"""Create one tunnel-only EC2 instance, or reuse it. Requires AWS CLI v2."""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANAGED_BY = "evios-ghost"
AMI_PARAMETER = (
    "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
)


def aws(service, operation, **body):
    # AWS CLI reads parameter files more than once; a pipe is not seekable.
    # NamedTemporaryFile is mode 0600 and is removed even when the CLI fails.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as payload:
        json.dump(body, payload)
        payload.flush()
        result = subprocess.run(
            [
                "aws",
                service,
                operation,
                "--region",
                os.environ["AWS_REGION"],
                "--cli-input-json",
                f"file://{payload.name}",
                "--output",
                "json",
                "--no-cli-pager",
            ],
            text=True,
            capture_output=True,
            timeout=120,
            env={**os.environ, "AWS_MAX_ATTEMPTS": "1", "AWS_CLI_AUTO_PROMPT": "off"},
        )
    if result.returncode:
        code = re.search(r"An error occurred \(([A-Za-z0-9_.-]+)\)", result.stderr)
        detail = code[1] if code else "CLI/authentication/network error"
        raise RuntimeError(
            f"AWS {operation} failed ({detail}); inspect EC2 Console before retrying."
        )
    return json.loads(result.stdout or "{}")


def tags(name):
    return [{"Key": "managed-by", "Value": MANAGED_BY}, {"Key": "Name", "Value": name}]


def instances(**filters):
    result = aws(
        "ec2",
        "describe-instances",
        Filters=[{"Name": key, "Values": [value]} for key, value in filters.items()],
    )
    return [
        instance
        for reservation in result["Reservations"]
        for instance in reservation["Instances"]
        if instance["State"]["Name"] != "terminated"
    ]


def cloud_config(name, key):
    files = {
        file: (ROOT / file).read_text()
        for file in ("compose.yml", "Caddyfile", "bootstrap.sh")
    }
    files.update(
        {"settings.json": json.dumps({"name": name}), "tailscale-authkey": key}
    )
    return "#cloud-config\n" + json.dumps(
        {
            "ssh_pwauth": False,
            "disable_root": True,
            "write_files": [
                {
                    "path": f"/opt/ghost/{file}",
                    "owner": "root:root",
                    "permissions": "0600",
                    "content": content,
                }
                for file, content in files.items()
            ],
            "runcmd": [["bash", "/opt/ghost/bootstrap.sh"]],
        }
    )


def provision():
    for key in ("AWS_REGION", "AWS_SUBNET_ID", "GHOST_NAME", "GHOST_INSTANCE_TYPE"):
        if not os.environ.get(key):
            raise RuntimeError(f"Missing {key}")
    name, size, subnet_id = (
        os.environ[key]
        for key in ("GHOST_NAME", "GHOST_INSTANCE_TYPE", "AWS_SUBNET_ID")
    )
    if not re.fullmatch(r"[a-z](?:[a-z0-9-]{0,48}[a-z0-9])?", name):
        raise RuntimeError(
            "GHOST_NAME must be 1–50 lowercase letters, digits or hyphens."
        )
    found = instances(**{"tag:managed-by": MANAGED_BY})
    if len(found) > 1 or (
        found and {t["Key"]: t["Value"] for t in found[0]["Tags"]}.get("Name") != name
    ):
        raise RuntimeError(
            "Existing Ghost deployment differs; keep its original name/region/account."
        )
    instance = found[0] if found else None
    if instance:
        if instance["InstanceType"] != size or instance["SubnetId"] != subnet_id:
            raise RuntimeError(
                "Keep the existing instance type/subnet; migration is separate maintenance."
            )
        if instance["State"]["Name"] not in ("pending", "running"):
            raise RuntimeError(
                "Existing instance is not running; inspect EC2 Console, do not recreate it."
            )
    else:
        if instances(**{"tag:Name": name}):
            raise RuntimeError(
                "Name belongs to an unmanaged instance; refusing to modify it."
            )
        key = os.environ.get("TS_AUTHKEY", "")
        if not re.fullmatch(r"tskey-auth-[A-Za-z0-9-]+", key):
            raise RuntimeError("First deployment needs a valid TS_AUTHKEY.")

    subnet = aws("ec2", "describe-subnets", SubnetIds=[subnet_id])["Subnets"][0]
    group_name = f"{name}-tunnel-only"
    groups = aws(
        "ec2",
        "describe-security-groups",
        Filters=[
            {"Name": "vpc-id", "Values": [subnet["VpcId"]]},
            {"Name": "group-name", "Values": [group_name]},
        ],
    )["SecurityGroups"]
    if groups:
        group = groups[0]
        labels = {tag["Key"]: tag["Value"] for tag in group.get("Tags", [])}
        if labels.get("managed-by") != MANAGED_BY or group["IpPermissions"]:
            raise RuntimeError(
                "Security group is unmanaged or has inbound rules; inspect EC2 Console."
            )
        group_id = group["GroupId"]
    elif instance:
        raise RuntimeError("Existing security group is missing; inspect EC2 Console.")
    else:
        group_id = aws(
            "ec2",
            "create-security-group",
            GroupName=group_name,
            Description="Ghost: outbound tunnels only, no inbound access",
            VpcId=subnet["VpcId"],
            TagSpecifications=[{"ResourceType": "security-group", "Tags": tags(name)}],
        )["GroupId"]

    if instance:
        if [g["GroupId"] for g in instance["SecurityGroups"]] != [group_id]:
            raise RuntimeError("Instance must have only its tunnel security group.")
        protected = aws(
            "ec2",
            "describe-instance-attribute",
            InstanceId=instance["InstanceId"],
            Attribute="disableApiTermination",
        )["DisableApiTermination"]["Value"]
        if not protected:
            raise RuntimeError(
                "Re-enable termination protection in EC2 Console before updating."
            )
    else:
        user_data = cloud_config(name, key).encode()
        if len(user_data) > 16384:
            raise RuntimeError("Bootstrap exceeds the EC2 16 KiB user-data limit.")
        image_id = aws("ssm", "get-parameter", Name=AMI_PARAMETER)["Parameter"]["Value"]
        instance = aws(
            "ec2",
            "run-instances",
            ImageId=image_id,
            InstanceType=size,
            MinCount=1,
            MaxCount=1,
            DisableApiTermination=True,
            ClientToken=hashlib.sha256(f"{MANAGED_BY}:{name}".encode()).hexdigest(),
            UserData=user_data.decode(),
            MetadataOptions={"HttpTokens": "required", "HttpPutResponseHopLimit": 1},
            NetworkInterfaces=[
                {
                    "DeviceIndex": 0,
                    "SubnetId": subnet_id,
                    "Groups": [group_id],
                    "AssociatePublicIpAddress": True,
                }
            ],
            BlockDeviceMappings=[
                {
                    "DeviceName": "/dev/sda1",
                    "Ebs": {
                        "VolumeSize": 30,
                        "VolumeType": "gp3",
                        "Encrypted": True,
                        "DeleteOnTermination": False,
                    },
                }
            ],
            TagSpecifications=[
                {"ResourceType": resource, "Tags": tags(name)}
                for resource in ("instance", "volume")
            ],
        )["Instances"][0]
    return name, instance["InstanceId"]


if __name__ == "__main__":
    try:
        print(*provision())
    except (
        RuntimeError,
        ValueError,
        KeyError,
        OSError,
        subprocess.TimeoutExpired,
    ) as error:
        print(f"Deployment stopped: {error}", file=sys.stderr)
        sys.exit(1)
