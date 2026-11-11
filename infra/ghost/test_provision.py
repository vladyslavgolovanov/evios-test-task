"""Exercise provisioning without an AWS account or paid resources."""

import copy
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import provision

ENV = {
    "AWS_REGION": "eu-central-1",
    "AWS_SUBNET_ID": "subnet-test",
    "GHOST_NAME": "ghost-demo",
    "GHOST_INSTANCE_TYPE": "t3.medium",
    "TS_AUTHKEY": "tskey-auth-test",
}


class Cloud:
    def __init__(self):
        self.instances = []
        self.groups = []
        self.launches = []
        self.lose_response = False
        self.protected = True

    def aws(self, service, operation, **body):
        if operation == "describe-instances":
            values = self.instances
            for item in body["Filters"]:
                key = item["Name"].removeprefix("tag:")
                values = [
                    i
                    for i in values
                    if {t["Key"]: t["Value"] for t in i["Tags"]}.get(key)
                    in item["Values"]
                ]
            return {"Reservations": [{"Instances": copy.deepcopy(values)}]}
        if operation == "describe-subnets":
            return {"Subnets": [{"SubnetId": "subnet-test", "VpcId": "vpc-test"}]}
        if operation == "describe-security-groups":
            return {"SecurityGroups": copy.deepcopy(self.groups)}
        if operation == "create-security-group":
            self.groups.append(
                {
                    "GroupId": "sg-test",
                    "IpPermissions": [],
                    "Tags": body["TagSpecifications"][0]["Tags"],
                }
            )
            return {"GroupId": "sg-test"}
        if operation == "describe-instance-attribute":
            return {"DisableApiTermination": {"Value": self.protected}}
        if operation == "get-parameter":
            return {"Parameter": {"Value": "ami-test"}}
        if operation == "run-instances":
            self.launches.append(copy.deepcopy(body))
            self.instances.append(
                {
                    "InstanceId": "i-test",
                    "InstanceType": body["InstanceType"],
                    "SubnetId": body["NetworkInterfaces"][0]["SubnetId"],
                    "Tags": body["TagSpecifications"][0]["Tags"],
                    "SecurityGroups": [{"GroupId": "sg-test"}],
                    "State": {"Name": "running"},
                }
            )
            if self.lose_response:
                raise RuntimeError("Connection lost after creation")
            return {"Instances": copy.deepcopy(self.instances)}
        raise AssertionError((service, operation))


class ProvisionTests(unittest.TestCase):
    def setUp(self):
        self.cloud = Cloud()
        environment = patch.dict(os.environ, ENV, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        aws = patch.object(provision, "aws", side_effect=self.cloud.aws)
        aws.start()
        self.addCleanup(aws.stop)

    def test_creation_is_private_protected_and_preserves_disk(self):
        self.assertEqual(provision.provision(), ("ghost-demo", "i-test"))
        self.assertEqual(self.cloud.groups[0]["IpPermissions"], [])
        payload = self.cloud.launches[0]
        self.assertEqual(payload["NetworkInterfaces"][0]["Groups"], ["sg-test"])
        self.assertTrue(payload["DisableApiTermination"])
        self.assertEqual(payload["MetadataOptions"]["HttpTokens"], "required")
        self.assertEqual(payload["MinCount"], 1)
        self.assertEqual(payload["MaxCount"], 1)
        disk = payload["BlockDeviceMappings"][0]["Ebs"]
        self.assertTrue(disk["Encrypted"])
        self.assertFalse(disk["DeleteOnTermination"])
        self.assertNotIn("KeyName", payload)
        self.assertNotIn("IamInstanceProfile", payload)
        data = payload["UserData"].encode()
        self.assertLessEqual(len(data), 16384)
        config = json.loads(data.decode().removeprefix("#cloud-config\n"))
        self.assertFalse(config["ssh_pwauth"])
        for file in config["write_files"]:
            self.assertEqual(file["permissions"], "0600")
            self.assertEqual(file["owner"], "root:root")
        files = {file["path"]: file["content"] for file in config["write_files"]}
        self.assertEqual(files["/opt/ghost/tailscale-authkey"], ENV["TS_AUTHKEY"])

    def test_repeat_reuses_instance_without_enrollment_key(self):
        provision.provision()
        del os.environ["TS_AUTHKEY"]
        self.assertEqual(provision.provision(), ("ghost-demo", "i-test"))
        self.assertEqual(len(self.cloud.launches), 1)
        self.assertEqual(len(self.cloud.groups), 1)

    def test_lost_response_does_not_create_duplicate(self):
        self.cloud.lose_response = True
        with self.assertRaisesRegex(RuntimeError, "Connection lost"):
            provision.provision()
        del os.environ["TS_AUTHKEY"]
        provision.provision()
        self.assertEqual(len(self.cloud.launches), 1)

    def test_foreign_name_collision_does_not_modify_resources(self):
        self.cloud.instances = [
            {
                "Tags": [{"Key": "Name", "Value": "ghost-demo"}],
                "State": {"Name": "running"},
            }
        ]
        with self.assertRaisesRegex(RuntimeError, "unmanaged instance"):
            provision.provision()
        self.assertFalse(self.cloud.groups)
        self.assertFalse(self.cloud.launches)

    def test_target_changes_are_rejected(self):
        provision.provision()
        for key in ("GHOST_NAME", "GHOST_INSTANCE_TYPE", "AWS_SUBNET_ID"):
            with self.subTest(key=key), patch.dict(os.environ, {key: "different"}):
                with self.assertRaises(RuntimeError):
                    provision.provision()
        self.assertEqual(len(self.cloud.launches), 1)

    def test_security_group_drift_is_rejected(self):
        provision.provision()
        self.cloud.groups[0]["IpPermissions"] = [{"FromPort": 22}]
        with self.assertRaisesRegex(RuntimeError, "inbound rules"):
            provision.provision()
        self.cloud.groups[0]["IpPermissions"] = []
        self.cloud.instances[0]["SecurityGroups"] = [{"GroupId": "sg-foreign"}]
        with self.assertRaisesRegex(RuntimeError, "only its tunnel"):
            provision.provision()

    def test_stopped_instance_or_disabled_protection_is_not_replaced(self):
        provision.provision()
        self.cloud.instances[0]["State"]["Name"] = "stopped"
        with self.assertRaisesRegex(RuntimeError, "not running"):
            provision.provision()
        self.cloud.instances[0]["State"]["Name"] = "running"
        self.cloud.protected = False
        with self.assertRaisesRegex(RuntimeError, "termination protection"):
            provision.provision()
        self.assertEqual(len(self.cloud.launches), 1)

    def test_invalid_inputs_fail_before_creating_resources(self):
        for key, value in (
            ("GHOST_NAME", "bad;name"),
            ("TS_AUTHKEY", ""),
            ("AWS_REGION", ""),
        ):
            with self.subTest(key=key), patch.dict(os.environ, {key: value}):
                with self.assertRaises(RuntimeError):
                    provision.provision()
        self.assertFalse(self.cloud.groups)
        self.assertFalse(self.cloud.launches)


class TransportTests(unittest.TestCase):
    def test_payload_is_private_removed_and_errors_do_not_leak_secrets(self):
        payload_path = None

        def cli(command, **kwargs):
            nonlocal payload_path
            payload_path = Path(
                command[command.index("--cli-input-json") + 1].removeprefix("file://")
            )
            self.assertEqual(payload_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(
                json.loads(payload_path.read_text()), {"UserData": "secret-body"}
            )
            self.assertNotIn("secret-body", " ".join(command))
            return subprocess.CompletedProcess(
                [], 255, "", "An error occurred (AccessDenied) secret-body"
            )

        with (
            patch.dict(os.environ, ENV),
            patch.object(provision.subprocess, "run", side_effect=cli),
        ):
            with self.assertRaisesRegex(RuntimeError, "AccessDenied") as caught:
                provision.aws("ec2", "run-instances", UserData="secret-body")
        self.assertNotIn("secret-body", str(caught.exception))
        self.assertFalse(payload_path.exists())
