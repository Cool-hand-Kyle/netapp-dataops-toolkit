#!/usr/bin/env python3

import base64
import json
import os
import re
from getpass import getpass

from netapp_dataops import traditional
from netapp_dataops.traditional import (
    clone_volume,
    InvalidConfigError,
    InvalidVolumeParameterError,
    InvalidSnapMirrorParameterError,
    InvalidSnapshotParameterError,
    APIConnectionError,
    mount_volume,
    MountOperationError,
    ConnectionTypeError,
    list_volumes,
    create_snapshot,
    create_volume,
    delete_snapshot,
    delete_volume,
    list_cloud_sync_relationships,
    list_snap_mirror_relationships,
    list_snapshots,
    prepopulate_flex_cache,
    pull_bucket_from_s3,
    pull_object_from_s3,
    push_directory_to_s3,
    push_file_to_s3,
    restore_snapshot,
    CloudSyncSyncOperationError,
    sync_cloud_sync_relationship,
    sync_snap_mirror_relationship,
    SnapMirrorSyncOperationError
)


## Define contents of help text
helpTextStandard = '''
The NetApp DataOps Toolkit is a Python library that makes it simple for data scientists and data engineers to perform various data management tasks, such as provisioning a new data volume, near-instantaneously cloning a data volume, and near-instantaneously snapshotting a data volume for traceability/baselining.

Basic Commands:

\tconfig\t\t\t\tCreate a new config file (a config file is required to perform other commands).
\thelp\t\t\t\tPrint help text.
\tversion\t\t\t\tPrint version details.

Data Volume Management Commands:
Note: To view details regarding options/arguments for a specific command, run the command with the '-h' or '--help' option.

\tclone volume\t\t\tCreate a new data volume that is an exact copy of an existing volume.
\tcreate volume\t\t\tCreate a new data volume.
\tdelete volume\t\t\tDelete an existing data volume.
\tlist volumes\t\t\tList all data volumes.
\tmount volume\t\t\tMount an existing data volume locally. Note: on Linux hosts - must be run as root.

Snapshot Management Commands:
Note: To view details regarding options/arguments for a specific command, run the command with the '-h' or '--help' option.

\tcreate snapshot\t\t\tCreate a new snapshot for a data volume.
\tdelete snapshot\t\t\tDelete an existing snapshot for a data volume.
\tlist snapshots\t\t\tList all snapshots for a data volume.
\trestore snapshot\t\tRestore a snapshot for a data volume (restore the volume to its exact state at the time that the snapshot was created).

Data Fabric Commands:
Note: To view details regarding options/arguments for a specific command, run the command with the '-h' or '--help' option.

\tlist cloud-sync-relationships\tList all existing Cloud Sync relationships.
\tsync cloud-sync-relationship\tTrigger a sync operation for an existing Cloud Sync relationship.
\tpull-from-s3 bucket\t\tPull the contents of a bucket from S3.
\tpull-from-s3 object\t\tPull an object from S3.
\tpush-to-s3 directory\t\tPush the contents of a directory to S3 (multithreaded).
\tpush-to-s3 file\t\t\tPush a file to S3.

Advanced Data Fabric Commands:
Note: To view details regarding options/arguments for a specific command, run the command with the '-h' or '--help' option.

\tprepopulate flexcache\t\tPrepopulate specific files/directories on a FlexCache volume (ONTAP 9.8 and above ONLY).
\tlist snapmirror-relationships\tList all existing SnapMirror relationships.
\tsync snapmirror-relationship\tTrigger a sync operation for an existing SnapMirror relationship.
'''
helpTextCloneVolume = '''
Command: clone volume

Create a new data volume that is an exact copy of an existing volume.

Required Options/Arguments:
\t-n, --name=\t\tName of new volume..
\t-v, --source-volume=\tName of volume to be cloned.

Optional Options/Arguments:
\t-g, --gid=\t\tUnix filesystem group id (gid) to apply when creating new volume (if not specified, gid of source volume will be retained) (Note: cannot apply gid of '0' when creating clone).
\t-h, --help\t\tPrint help text.
\t-m, --mountpoint=\tLocal mountpoint to mount new volume at after creating. If not specified, new volume will not be mounted locally. On Linux hosts - if specified, must be run as root.
\t-s, --source-snapshot=\tName of the snapshot to be cloned (if specified, the clone will be created from a specific snapshot on the source volume as opposed to the current state of the volume).
\t-u, --uid=\t\tUnix filesystem user id (uid) to apply when creating new volume (if not specified, uid of source volume will be retained) (Note: cannot apply uid of '0' when creating clone).
\t-x, --readonly\t\tRead-only option for mounting volumes locally.

Examples (basic usage):
\tnetapp_dataops_cli.py clone volume --name=project1 --source-volume=gold_dataset
\tnetapp_dataops_cli.py clone volume -n project2 -v gold_dataset -s snap1
\tsudo -E netapp_dataops_cli.py clone volume --name=project1 --source-volume=gold_dataset --mountpoint=~/project1 -x

Examples (advanced usage):
\tnetapp_dataops_cli.py clone volume -n testvol -v gold_dataset -u 1000 -g 1000
'''
helpTextConfig = '''
Command: config

Create a new config file (a config file is required to perform other commands).

No additional options/arguments required.
'''
helpTextCreateSnapshot = '''
Command: create snapshot

Create a new snapshot for a data volume.

Required Options/Arguments:
\t-v, --volume=\tName of volume.

Optional Options/Arguments:
\t-h, --help\tPrint help text.
\t-n, --name=\tName of new snapshot. If not specified, will be set to 'netapp_dataops_<timestamp>'.

Examples:
\tnetapp_dataops_cli.py create snapshot --volume=project1 --name=snap1
\tnetapp_dataops_cli.py create snapshot -v project2 -n final_dataset
\tnetapp_dataops_cli.py create snapshot --volume=test1
'''
helpTextCreateVolume = '''
Command: create volume

Create a new data volume.

Required Options/Arguments:
\t-n, --name=\t\tName of new volume.
\t-s, --size=\t\tSize of new volume. Format: '1024MB', '100GB', '10TB', etc.

Optional Options/Arguments:
\t-a, --aggregate=\tAggregate to use when creating new volume (flexvol volumes only).
\t-d, --snapshot-policy=\tSnapshot policy to apply for new volume.
\t-e, --export-policy=\tNFS export policy to use when exporting new volume.
\t-g, --gid=\t\tUnix filesystem group id (gid) to apply when creating new volume (ex. '0' for root group).
\t-h, --help\t\tPrint help text.
\t-m, --mountpoint=\tLocal mountpoint to mount new volume at after creating. If not specified, new volume will not be mounted locally. On Linux hosts - if specified, must be run as root.
\t-p, --permissions=\tUnix filesystem permissions to apply when creating new volume (ex. '0777' for full read/write permissions for all users and groups).
\t-r, --guarantee-space\tGuarantee sufficient storage space for full capacity of the volume (i.e. do not use thin provisioning).
\t-t, --type=\t\tVolume type to use when creating new volume (flexgroup/flexvol).
\t-u, --uid=\t\tUnix filesystem user id (uid) to apply when creating new volume (ex. '0' for root user).
\t-x, --readonly\t\tRead-only option for mounting volumes locally.

Examples (basic usage):
\tnetapp_dataops_cli.py create volume --name=project1 --size=10GB
\tnetapp_dataops_cli.py create volume -n datasets -s 10TB
\tsudo -E netapp_dataops_cli.py create volume --name=project2 --size=2TB --mountpoint=~/project2 --readonly

Examples (advanced usage):
\tsudo -E netapp_dataops_cli.py create volume --name=project1 --size=10GB --permissions=0755 --type=flexvol --mountpoint=~/project1 -x
\tsudo -E netapp_dataops_cli.py create volume --name=project2_flexgroup --size=2TB --type=flexgroup --mountpoint=/mnt/project2
\tnetapp_dataops_cli.py create volume --name=testvol --size=10GB --type=flexvol --aggregate=n2_data
\tnetapp_dataops_cli.py create volume -n testvol -s 10GB -t flexvol -p 0755 -u 1000 -g 1000
\tsudo -E netapp_dataops_cli.py create volume -n vol1 -s 5GB -t flexvol --export-policy=team1 -m /mnt/vol1
\tnetapp_dataops_cli.py create vol -n test2 -s 10GB -t flexvol --snapshot-policy=default
'''
helpTextDeleteSnapshot = '''
Command: delete snapshot

Delete an existing snapshot for a data volume.

Required Options/Arguments:
\t-n, --name=\tName of snapshot to be deleted.
\t-v, --volume=\tName of volume.

Optional Options/Arguments:
\t-h, --help\tPrint help text.

Examples:
\tnetapp_dataops_cli.py delete snapshot --volume=project1 --name=snap1
\tnetapp_dataops_cli.py delete snapshot -v project2 -n netapp_dataops_20201113_221917
'''
helpTextDeleteVolume = '''
Command: delete volume

Delete an existing data volume.

Required Options/Arguments:
\t-n, --name=\tName of volume to be deleted.

Optional Options/Arguments:
\t-f, --force\tDo not prompt user to confirm operation.
\t-h, --help\tPrint help text.

Examples:
\tnetapp_dataops_cli.py delete volume --name=project1
\tnetapp_dataops_cli.py delete volume -n project2
'''
helpTextListCloudSyncRelationships = '''
Command: list cloud-sync-relationships

List all existing Cloud Sync relationships.

No additional options/arguments required.
'''
helpTextListSnapMirrorRelationships = '''
Command: list snapmirror-relationships

List all SnapMirror relationships.

No additional options/arguments required.
'''
helpTextListSnapshots = '''
Command: list snapshots

List all snapshots for a data volume.

Required Options/Arguments:
\t-v, --volume=\tName of volume.

Optional Options/Arguments:
\t-h, --help\tPrint help text.

Examples:
\tnetapp_dataops_cli.py list snapshots --volume=project1
\tnetapp_dataops_cli.py list snapshots -v test1
'''
helpTextListVolumes = '''
Command: list volumes

List all data volumes.

No options/arguments are required.

Optional Options/Arguments:
\t-h, --help\t\t\t\tPrint help text.
\t-s, --include-space-usage-details\tInclude storage space usage details in output (see README for explanation).

Examples:
\tnetapp_dataops_cli.py list volumes
\tnetapp_dataops_cli.py list volumes --include-space-usage-details
'''
helpTextMountVolume = '''
Command: mount volume

Mount an existing data volume locally.

Requirement: On Linux hosts, must be run as root.

Required Options/Arguments:
\t-m, --mountpoint=\tLocal mountpoint to mount volume at.
\t-n, --name=\t\tName of volume.

Optional Options/Arguments:
\t-h, --help\t\tPrint help text.
\t-x, --readonly\t\tChoose whether to mount volume locally as read-only.
Examples:
\tsudo -E netapp_dataops_cli.py mount volume --name=project1 --mountpoint=/mnt/project1
\tsudo -E netapp_dataops_cli.py mount volume -m ~/testvol -n testvol
\tsudo -E netapp_dataops_cli.py mount volume --name=project1 --mountpoint=/mnt/project1 --readonly
'''
helpTextPullFromS3Bucket = '''
Command: pull-from-s3 bucket

Pull the contents of a bucket from S3 (multithreaded).

Note: To pull to a data volume, the volume must be mounted locally.

Warning: This operation has not been tested at scale and may not be appropriate for extremely large datasets.

Required Options/Arguments:
\t-b, --bucket=\t\tS3 bucket to pull from.
\t-d, --directory=\tLocal directory to save contents of bucket to.

Optional Options/Arguments:
\t-h, --help\t\tPrint help text.
\t-p, --key-prefix=\tObject key prefix (pull will be limited to objects with key that starts with this prefix).

Examples:
\tnetapp_dataops_cli.py pull-from-s3 bucket --bucket=project1 --directory=/mnt/project1
\tnetapp_dataops_cli.py pull-from-s3 bucket -b project1 -p project1/ -d ./project1/
'''
helpTextPullFromS3Object = '''
Command: pull-from-s3 object

Pull an object from S3.

Note: To pull to a data volume, the volume must be mounted locally.

Required Options/Arguments:
\t-b, --bucket=\t\tS3 bucket to pull from.
\t-k, --key=\t\tKey of S3 object to pull.

Optional Options/Arguments:
\t-f, --file=\t\tLocal filepath (including filename) to save object to (if not specified, value of -k/--key argument will be used)
\t-h, --help\t\tPrint help text.

Examples:
\tnetapp_dataops_cli.py pull-from-s3 object --bucket=project1 --key=data.csv --file=./project1/data.csv
\tnetapp_dataops_cli.py pull-from-s3 object -b project1 -k data.csv
'''
helpTextPushToS3Directory = '''
Command: push-to-s3 directory

Push the contents of a directory to S3 (multithreaded).

Note: To push from a data volume, the volume must be mounted locally.

Warning: This operation has not been tested at scale and may not be appropriate for extremely large datasets.

Required Options/Arguments:
\t-b, --bucket=\t\tS3 bucket to push to.
\t-d, --directory=\tLocal directory to push contents of.

Optional Options/Arguments:
\t-e, --extra-args=\tExtra args to apply to newly-pushed S3 objects (For details on this field, refer to https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-uploading-files.html#the-extraargs-parameter).
\t-h, --help\t\tPrint help text.
\t-p, --key-prefix=\tPrefix to add to key for newly-pushed S3 objects (Note: by default, key will be local filepath relative to directory being pushed).

Examples:
\tnetapp_dataops_cli.py push-to-s3 directory --bucket=project1 --directory=/mnt/project1
\tnetapp_dataops_cli.py push-to-s3 directory -b project1 -d /mnt/project1 -p project1/ -e '{"Metadata": {"mykey": "myvalue"}}'
'''
helpTextPushToS3File = '''
Command: push-to-s3 file

Push a file to S3.

Note: To push from a data volume, the volume must be mounted locally.

Required Options/Arguments:
\t-b, --bucket=\t\tS3 bucket to push to.
\t-f, --file=\t\tLocal file to push.

Optional Options/Arguments:
\t-e, --extra-args=\tExtra args to apply to newly-pushed S3 object (For details on this field, refer to https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-uploading-files.html#the-extraargs-parameter).
\t-h, --help\t\tPrint help text.
\t-k, --key=\t\tKey to assign to newly-pushed S3 object (if not specified, key will be set to value of -f/--file argument).

Examples:
\tnetapp_dataops_cli.py push-to-s3 file --bucket=project1 --file=data.csv
\tnetapp_dataops_cli.py push-to-s3 file -b project1 -k data.csv -f /mnt/project1/data.csv -e '{"Metadata": {"mykey": "myvalue"}}'
'''
helpTextPrepopulateFlexCache = '''
Command: prepopulate flexcache

Prepopulate specific files/directories on a FlexCache volume.

Compatibility: ONTAP 9.8 and above ONLY

Required Options/Arguments:
\t-n, --name=\tName of FlexCache volume.
\t-p, --paths=\tComma-separated list of dirpaths/filepaths to prepopulate.

Optional Options/Arguments:
\t-h, --help\tPrint help text.

Examples:
\tnetapp_dataops_cli.py prepopulate flexcache --name=project1 --paths=/datasets/project1,/datasets/project2
\tnetapp_dataops_cli.py prepopulate flexcache -n test1 -p /datasets/project1,/datasets/project2
'''
helpTextRestoreSnapshot = '''
Command: restore snapshot

Restore a snapshot for a data volume (restore the volume to its exact state at the time that the snapshot was created).

Required Options/Arguments:
\t-n, --name=\tName of snapshot to be restored.
\t-v, --volume=\tName of volume.

Optional Options/Arguments:
\t-f, --force\tDo not prompt user to confirm operation.
\t-h, --help\tPrint help text.

Examples:
\tnetapp_dataops_cli.py restore snapshot --volume=project1 --name=snap1
\tnetapp_dataops_cli.py restore snapshot -v project2 -n netapp_dataops_20201113_221917
'''
helpTextSyncCloudSyncRelationship = '''
Command: sync cloud-sync-relationship

Trigger a sync operation for an existing Cloud Sync relationship.

Tip: Run `netapp_dataops_cli.py list cloud-sync-relationships` to obtain relationship ID.

Required Options/Arguments:
\t-i, --id=\tID of the relationship for which the sync operation is to be triggered.

Optional Options/Arguments:
\t-h, --help\tPrint help text.
\t-w, --wait\tWait for sync operation to complete before exiting.

Examples:
\tnetapp_dataops_cli.py sync cloud-sync-relationship --id=5ed00996ca85650009a83db2
\tnetapp_dataops_cli.py sync cloud-sync-relationship -i 5ed00996ca85650009a83db2 -w
'''
helpTextSyncSnapMirrorRelationship = '''
Command: sync snapmirror-relationship

Trigger a sync operation for an existing SnapMirror relationship.

Tip: Run `netapp_dataops_cli.py list snapmirror-relationships` to obtain relationship UUID.

Required Options/Arguments:
\t-i, --uuid=\tUUID of the relationship for which the sync operation is to be triggered.

Optional Options/Arguments:
\t-h, --help\tPrint help text.
\t-w, --wait\tWait for sync operation to complete before exiting.

Examples:
\tnetapp_dataops_cli.py sync snapmirror-relationship --uuid=132aab2c-4557-11eb-b542-005056932373
\tnetapp_dataops_cli.py sync snapmirror-relationship -i 132aab2c-4557-11eb-b542-005056932373 -w
'''


## Function for creating config file
def createConfig(configDirPath: str = "~/.netapp_dataops", configFilename: str = "config.json", connectionType: str = "ONTAP"):
    # Check to see if user has an existing config file
    configDirPath = os.path.expanduser(configDirPath)
    configFilePath = os.path.join(configDirPath, configFilename)
    if os.path.isfile(configFilePath):
        print("You already have an existing config file. Creating a new config file will overwrite this existing config.")
        # If existing config file is present, ask user if they want to proceed
        # Verify value entered; prompt user to re-enter if invalid
        while True:
            proceed = input("Are you sure that you want to proceed? (yes/no): ")
            if proceed in ("yes", "Yes", "YES"):
                break
            elif proceed in ("no", "No", "NO"):
                sys.exit(0)
            else:
                print("Invalid value. Must enter 'yes' or 'no'.")

    # Instantiate dict for storing connection details
    config = dict()

    if connectionType == "ONTAP":
        config["connectionType"] = connectionType

        # Prompt user to enter config details
        config["hostname"] = input("Enter ONTAP management LIF hostname or IP address (Recommendation: Use SVM management interface): ")
        config["svm"] = input("Enter SVM (Storage VM) name: ")
        config["dataLif"] = input("Enter SVM NFS data LIF hostname or IP address: ")

        # Prompt user to enter default volume type
        # Verify value entered; promopt user to re-enter if invalid
        while True:
            config["defaultVolumeType"] = input("Enter default volume type to use when creating new volumes (flexgroup/flexvol) [flexgroup]: ")
            if not config["defaultVolumeType"] :
                config["defaultVolumeType"] = "flexgroup"
                break
            elif config["defaultVolumeType"] in ("flexgroup", "FlexGroup"):
                config["defaultVolumeType"] = "flexgroup"
                break
            elif config["defaultVolumeType"] in ("flexvol", "FlexVol"):
                config["defaultVolumeType"] = "flexvol"
                break
            else:
                print("Invalid value. Must enter 'flexgroup' or 'flexvol'.")

        # prompt user to enter default export policy
        config["defaultExportPolicy"] = input("Enter export policy to use by default when creating new volumes [default]: ")
        if not config["defaultExportPolicy"]:
            config["defaultExportPolicy"] = "default"

        # prompt user to enter default snapshot policy
        config["defaultSnapshotPolicy"] = input("Enter snapshot policy to use by default when creating new volumes [none]: ")
        if not config["defaultSnapshotPolicy"]:
            config["defaultSnapshotPolicy"] = "none"

        # Prompt user to enter default uid, gid, and unix permissions
        # Verify values entered; promopt user to re-enter if invalid
        while True:
            config["defaultUnixUID"] = input("Enter unix filesystem user id (uid) to apply by default when creating new volumes (ex. '0' for root user) [0]: ")
            if not config["defaultUnixUID"]:
                config["defaultUnixUID"] = "0"
                break
            try:
                int(config["defaultUnixUID"])
                break
            except:
                print("Invalid value. Must enter an integer.")
        while True:
            config["defaultUnixGID"] = input("Enter unix filesystem group id (gid) to apply by default when creating new volumes (ex. '0' for root group) [0]: ")
            if not config["defaultUnixGID"]:
                config["defaultUnixGID"] = "0"
                break
            try:
                int(config["defaultUnixGID"])
                break
            except:
                print("Invalid value. Must enter an integer.")
        while True:
            config["defaultUnixPermissions"] = input("Enter unix filesystem permissions to apply by default when creating new volumes (ex. '0777' for full read/write permissions for all users and groups) [0777]: ")
            if not config["defaultUnixPermissions"] :
                config["defaultUnixPermissions"] = "0777"
                break
            elif not re.search("^0[0-7]{3}", config["defaultUnixPermissions"]):
                print("Invalud value. Must enter a valid unix permissions value. Acceptable values are '0777', '0755', '0744', etc.")
            else:
                break

        # Prompt user to enter additional config details
        config["defaultAggregate"] = input("Enter aggregate to use by default when creating new FlexVol volumes: ")
        config["username"] = input("Enter ONTAP API username (Recommendation: Use SVM account): ")
        passwordString = getpass("Enter ONTAP API password (Recommendation: Use SVM account): ")

        # Convert password to base64 enconding
        passwordBytes = passwordString.encode("ascii")
        passwordBase64Bytes = base64.b64encode(passwordBytes)
        config["password"] = passwordBase64Bytes.decode("ascii")

        # Prompt user to enter value denoting whether or not to verify SSL cert when calling ONTAP API
        # Verify value entered; prompt user to re-enter if invalid
        while True:
            verifySSLCert = input("Verify SSL certificate when calling ONTAP API (true/false): ")
            if verifySSLCert in ("true", "True") :
                config["verifySSLCert"] = True
                break
            elif verifySSLCert in ("false", "False") :
                config["verifySSLCert"] = False
                break
            else:
                print("Invalid value. Must enter 'true' or 'false'.")

    else:
        raise ConnectionTypeError()

    # Ask user if they want to use cloud sync functionality
    # Verify value entered; prompt user to re-enter if invalid
    while True:
        useCloudSync = input("Do you intend to use this toolkit to trigger Cloud Sync operations? (yes/no): ")

        if useCloudSync in ("yes", "Yes", "YES"):
            # Prompt user to enter cloud central refresh token
            print("Note: If you do not have a Cloud Central refresh token, visit https://services.cloud.netapp.com/refresh-token to create one.")
            refreshTokenString = getpass("Enter Cloud Central refresh token: ")

            # Convert refresh token to base64 enconding
            refreshTokenBytes = refreshTokenString.encode("ascii")
            refreshTokenBase64Bytes = base64.b64encode(refreshTokenBytes)
            config["cloudCentralRefreshToken"] = refreshTokenBase64Bytes.decode("ascii")

            break

        elif useCloudSync in ("no", "No", "NO"):
            break

        else:
            print("Invalid value. Must enter 'yes' or 'no'.")

    # Ask user if they want to use S3 functionality
    # Verify value entered; prompt user to re-enter if invalid
    while True:
        useS3 = input("Do you intend to use this toolkit to push/pull from S3? (yes/no): ")

        if useS3 in ("yes", "Yes", "YES"):
            # Promt user to enter S3 endpoint details
            config["s3Endpoint"] = input("Enter S3 endpoint: ")

            # Prompt user to enter S3 credentials
            config["s3AccessKeyId"] = input("Enter S3 Access Key ID: ")
            s3SecretAccessKeyString = getpass("Enter S3 Secret Access Key: ")

            # Convert refresh token to base64 enconding
            s3SecretAccessKeyBytes = s3SecretAccessKeyString.encode("ascii")
            s3SecretAccessKeyBase64Bytes = base64.b64encode(s3SecretAccessKeyBytes)
            config["s3SecretAccessKey"] = s3SecretAccessKeyBase64Bytes.decode("ascii")

            # Prompt user to enter value denoting whether or not to verify SSL cert when calling S3 API
            # Verify value entered; prompt user to re-enter if invalid
            while True:
                s3VerifySSLCert = input("Verify SSL certificate when calling S3 API (true/false): ")
                if s3VerifySSLCert in ("true", "True"):
                    config["s3VerifySSLCert"] = True
                    config["s3CACertBundle"] = input("Enter CA cert bundle to use when calling S3 API (optional) []: ")
                    break
                elif s3VerifySSLCert in ("false", "False"):
                    config["s3VerifySSLCert"] = False
                    config["s3CACertBundle"] = ""
                    break
                else:
                    print("Invalid value. Must enter 'true' or 'false'.")

            break

        elif useS3 in ("no", "No", "NO"):
            break

        else:
            print("Invalid value. Must enter 'yes' or 'no'.")

    # Create config dir if it doesn't already exist
    try:
        os.mkdir(configDirPath)
    except FileExistsError :
        pass

    # Create config file in config dir
    with open(configFilePath, 'w') as configFile:
        # Write connection details to config file
        json.dump(config, configFile)

    print("Created config file: '" + configFilePath + "'.")


def getTarget(args: list) -> str:
    try:
        target = args[2]
    except:
        handleInvalidCommand()
    return target


def handleInvalidCommand(helpText: str = helpTextStandard, invalidOptArg: bool = False):
    if invalidOptArg:
        print("Error: Invalid option/argument.")
    else:
        print("Error: Invalid command.")
    print(helpText)
    sys.exit(1)


## Main function
if __name__ == '__main__':
    import sys, getopt

    # Get desired action from command line args
    try:
        action = sys.argv[1]
    except:
        handleInvalidCommand()

    # Invoke desired action
    if action == "clone":
        # Get desired target from command line args
        target = getTarget(sys.argv)

        # Invoke desired action based on target
        if target in ("volume", "vol"):
            newVolumeName = None
            sourceVolumeName = None
            sourceSnapshotName = None
            mountpoint = None
            unixUID = None
            unixGID = None
            readonly = False

            # Get command line options
            try:
                opts, args = getopt.getopt(sys.argv[3:], "hn:v:s:m:u:g:x", ["help", "name=", "source-volume=", "source-snapshot=", "mountpoint=", "uid=", "gid=", "readonly"])
            except:
                handleInvalidCommand(helpText=helpTextCloneVolume, invalidOptArg=True)

            # Parse command line options
            for opt, arg in opts:
                if opt in ("-h", "--help"):
                    print(helpTextCloneVolume)
                    sys.exit(0)
                elif opt in ("-n", "--name"):
                    newVolumeName = arg
                elif opt in ("-v", "--source-volume"):
                    sourceVolumeName = arg
                elif opt in ("-s", "--source-snapshot"):
                    sourceSnapshotName = arg
                elif opt in ("-m", "--mountpoint"):
                    mountpoint = arg
                elif opt in ("-u", "--uid"):
                    unixUID = arg
                elif opt in ("-g", "--gid"):
                    unixGID = arg
                elif opt in ("-x", "--readonly"):
                    readonly = True

            # Check for required options
            if not newVolumeName or not sourceVolumeName:
                handleInvalidCommand(helpText=helpTextCloneVolume, invalidOptArg=True)
            if (unixUID and not unixGID) or (unixGID and not unixUID):
                print("Error: if either one of -u/--uid or -g/--gid is spefied, then both must be specified.")
                handleInvalidCommand(helpText=helpTextCloneVolume, invalidOptArg=True)

            # Clone volume
            try:
                clone_volume(new_volume_name=newVolumeName, source_volume_name=sourceVolumeName, source_snapshot_name=sourceSnapshotName,
                             mountpoint=mountpoint, unix_uid=unixUID, unix_gid=unixGID, readonly=readonly, print_output=True)
            except (InvalidConfigError, APIConnectionError, InvalidSnapshotParameterError, InvalidVolumeParameterError,
                    MountOperationError):
                sys.exit(1)

        else:
            handleInvalidCommand()

    elif action in ("config", "setup"):
        if len(sys.argv) > 2 :
            if sys.argv[2] in ("-h", "--help"):
                print(helpTextConfig)
                sys.exit(0)
            else:
                handleInvalidCommand(helpTextConfig, invalidOptArg=True)

        #connectionType = input("Enter connection type (ONTAP): ")
        connectionType = "ONTAP"

        # Create config file
        createConfig(connectionType=connectionType)

    elif action == "create":
        # Get desired target from command line args
        target = getTarget(sys.argv)

        # Invoke desired action based on target
        if target in ("snapshot", "snap"):
            volumeName = None
            snapshotName = None

            # Get command line options
            try:
                opts, args = getopt.getopt(sys.argv[3:], "hn:v:", ["help", "name=", "volume="])
            except:
                handleInvalidCommand(helpText=helpTextCreateSnapshot, invalidOptArg=True)

            # Parse command line options
            for opt, arg in opts:
                if opt in ("-h", "--help") :
                    print(helpTextCreateSnapshot)
                    sys.exit(0)
                elif opt in ("-n", "--name"):
                    snapshotName = arg
                elif opt in ("-v", "--volume"):
                    volumeName = arg


            # Check for required options
            if not volumeName:
                handleInvalidCommand(helpText=helpTextCreateSnapshot, invalidOptArg=True)

            # Create snapshot
            try:
                create_snapshot(volume_name=volumeName, snapshot_name=snapshotName, print_output=True)
            except (InvalidConfigError, APIConnectionError, InvalidVolumeParameterError):
                sys.exit(1)

        elif target in ("volume", "vol"):
            volumeName = None
            volumeSize = None
            guaranteeSpace = False
            volumeType = None
            unixPermissions = None
            unixUID = None
            unixGID = None
            exportPolicy = None
            snapshotPolicy = None
            mountpoint = None
            aggregate = None
            readonly = False

            # Get command line options
            try:
                opts, args = getopt.getopt(sys.argv[3:], "hn:s:rt:p:u:g:e:d:m:a:x", ["help", "name=", "size=", "guarantee-space", "type=", "permissions=", "uid=", "gid=", "export-policy=", "snapshot-policy=", "mountpoint=", "aggregate=", "readonly"])
            except:
                handleInvalidCommand(helpText=helpTextCreateVolume, invalidOptArg=True)

            # Parse command line options
            for opt, arg in opts:
                if opt in ("-h", "--help"):
                    print(helpTextCreateVolume)
                    sys.exit(0)
                elif opt in ("-n", "--name"):
                    volumeName = arg
                elif opt in ("-s", "--size"):
                    volumeSize = arg
                elif opt in ("-r", "--guarantee-space"):
                    guaranteeSpace = True
                elif opt in ("-t", "--type"):
                    volumeType = arg
                elif opt in ("-p", "--permissions"):
                    unixPermissions = arg
                elif opt in ("-u", "--uid"):
                    unixUID = arg
                elif opt in ("-g", "--gid"):
                    unixGID = arg
                elif opt in ("-e", "--export-policy"):
                    exportPolicy = arg
                elif opt in ("-d", "--snapshot-policy"):
                    snapshotPolicy = arg
                elif opt in ("-m", "--mountpoint"):
                    mountpoint = arg
                elif opt in ("-a", "--aggregate"):
                    aggregate = arg
                elif opt in ("-x", "--readonly"):
                    readonly = True

            # Check for required options
            if not volumeName or not volumeSize:
                handleInvalidCommand(helpText=helpTextCreateVolume, invalidOptArg=True)
            if (unixUID and not unixGID) or (unixGID and not unixUID):
                print("Error: if either one of -u/--uid or -g/--gid is spefied, then both must be specified.")
                handleInvalidCommand(helpText=helpTextCreateVolume, invalidOptArg=True)

            # Create volume
            try:
                create_volume(volume_name=volumeName, volume_size=volumeSize, guarantee_space=guaranteeSpace, volume_type=volumeType, unix_permissions=unixPermissions, unix_uid=unixUID,
                              unix_gid=unixGID, export_policy=exportPolicy, snapshot_policy=snapshotPolicy, aggregate=aggregate, mountpoint=mountpoint, readonly=readonly, print_output=True)
            except (InvalidConfigError, APIConnectionError, InvalidVolumeParameterError, MountOperationError):
                sys.exit(1)

        else:
            handleInvalidCommand()

    elif action in ("delete", "del", "rm"):
        # Get desired target from command line args
        target = getTarget(sys.argv)

        # Invoke desired action based on target
        if target in ("snapshot", "snap"):
            volumeName = None
            snapshotName = None

            # Get command line options
            try:
                opts, args = getopt.getopt(sys.argv[3:], "hn:v:", ["help", "name=", "volume="])
            except:
                handleInvalidCommand(helpText=helpTextDeleteSnapshot, invalidOptArg=True)

            # Parse command line options
            for opt, arg in opts:
                if opt in ("-h", "--help"):
                    print(helpTextDeleteSnapshot)
                    sys.exit(0)
                elif opt in ("-n", "--name"):
                    snapshotName = arg
                elif opt in ("-v", "--volume"):
                    volumeName = arg

            # Check for required options
            if not volumeName or not snapshotName:
                handleInvalidCommand(helpText=helpTextDeleteSnapshot, invalidOptArg=True)

            # Delete snapshot
            try:
                delete_snapshot(volume_name=volumeName, snapshot_name=snapshotName, print_output=True)
            except (InvalidConfigError, APIConnectionError, InvalidSnapshotParameterError, InvalidVolumeParameterError):
                sys.exit(1)

        elif target in ("volume", "vol"):
            volumeName = None
            force = False

            # Get command line options
            try:
                opts, args = getopt.getopt(sys.argv[3:], "hn:f", ["help", "name=", "force"])
            except:
                handleInvalidCommand(helpText=helpTextDeleteVolume, invalidOptArg=True)

            # Parse command line options
            for opt, arg in opts:
                if opt in ("-h", "--help"):
                    print(helpTextDeleteVolume)
                    sys.exit(0)
                elif opt in ("-n", "--name"):
                    volumeName = arg
                elif opt in ("-f", "--force"):
                    force = True

            # Check for required options
            if not volumeName:
                handleInvalidCommand(helpText=helpTextDeleteVolume, invalidOptArg=True)

            # Confirm delete operation
            if not force:
                print("Warning: All data and snapshots associated with the volume will be permanently deleted.")
                while True:
                    proceed = input("Are you sure that you want to proceed? (yes/no): ")
                    if proceed in ("yes", "Yes", "YES"):
                        break
                    elif proceed in ("no", "No", "NO"):
                        sys.exit(0)
                    else:
                        print("Invalid value. Must enter 'yes' or 'no'.")

            # Delete volume
            try:
                delete_volume(volume_name=volumeName, print_output=True)
            except (InvalidConfigError, APIConnectionError, InvalidVolumeParameterError):
                sys.exit(1)

        else:
            handleInvalidCommand()

    elif action in ("help", "h", "-h", "--help"):
        print(helpTextStandard)

    elif action in ("list", "ls"):
        # Get desired target from command line args
        target = getTarget(sys.argv)

        # Invoke desired action based on target
        if target in ("cloud-sync-relationship", "cloud-sync", "cloud-sync-relationships", "cloud-syncs") :
            # Check command line options
            if len(sys.argv) > 3:
                if sys.argv[3] in ("-h", "--help"):
                    print(helpTextListCloudSyncRelationships)
                    sys.exit(0)
                else:
                    handleInvalidCommand(helpTextListCloudSyncRelationships, invalidOptArg=True)

            # List cloud sync relationships
            try:
                list_cloud_sync_relationships(print_output=True)
            except (InvalidConfigError, APIConnectionError):
                sys.exit(1)

        elif target in ("snapmirror-relationship", "snapmirror", "snapmirror-relationships", "snapmirrors"):
            # Check command line options
            if len(sys.argv) > 3:
                if sys.argv[3] in ("-h", "--help"):
                    print(helpTextListSnapMirrorRelationships)
                    sys.exit(0)
                else:
                    handleInvalidCommand(helpTextListSnapMirrorRelationships, invalidOptArg=True)

            # List cloud sync relationships
            try:
                list_snap_mirror_relationships(print_output=True)
            except (InvalidConfigError, APIConnectionError):
                sys.exit(1)

        elif target in ("snapshot", "snap", "snapshots", "snaps"):
            volumeName = None

            # Get command line options
            try:
                opts, args = getopt.getopt(sys.argv[3:], "hv:", ["help", "volume="])
            except:
                handleInvalidCommand(helpText=helpTextListSnapshots, invalidOptArg=True)

            # Parse command line options
            for opt, arg in opts:
                if opt in ("-h", "--help") :
                    print(helpTextListSnapshots)
                    sys.exit(0)
                elif opt in ("-v", "--volume"):
                    volumeName = arg

            # Check for required options
            if not volumeName:
                handleInvalidCommand(helpText=helpTextListSnapshots, invalidOptArg=True)

            # List volumes
            try:
                list_snapshots(volume_name=volumeName, print_output=True)
            except (InvalidConfigError, APIConnectionError, InvalidVolumeParameterError):
                sys.exit(1)

        elif target in ("volume", "vol", "volumes", "vols"):
            includeSpaceUsageDetails = False

            # Get command line options
            try:
                opts, args = getopt.getopt(sys.argv[3:], "hs", ["help", "include-space-usage-details"])
            except:
                handleInvalidCommand(helpText=helpTextListVolumes, invalidOptArg=True)

            # Parse command line options
            for opt, arg in opts:
                if opt in ("-h", "--help") :
                    print(helpTextListVolumes)
                    sys.exit(0)
                elif opt in ("-s", "--include-space-usage-details"):
                    includeSpaceUsageDetails = True

            # List volumes
            try:
                list_volumes(check_local_mounts=True, include_space_usage_details=includeSpaceUsageDetails, print_output=True)
            except (InvalidConfigError, APIConnectionError) :
                sys.exit(1)

        else:
            handleInvalidCommand()

    elif action == "mount":
        # Get desired target from command line args
        target = getTarget(sys.argv)

        # Invoke desired action based on target
        if target in ("volume", "vol"):
            volumeName = None
            mountpoint = None
            readonly = False
            # Get command line options
            try:
                opts, args = getopt.getopt(sys.argv[3:], "hn:m:x", ["help", "name=", "mountpoint=", "readonly"])
            except:
                handleInvalidCommand(helpText=helpTextMountVolume, invalidOptArg=True)

            # Parse command line options
            for opt, arg in opts:
                if opt in ("-h", "--help"):
                    print(helpTextMountVolume)
                    sys.exit(0)
                elif opt in ("-n", "--name"):
                    volumeName = arg
                elif opt in ("-m", "--mountpoint"):
                    mountpoint = arg
                elif opt in ("-x", "--readonly"):
                    readonly = True
            print(readonly)

            # Mount volume
            try:
                mount_volume(volume_name=volumeName, mountpoint=mountpoint, readonly=readonly, print_output=True)
            except (InvalidConfigError, APIConnectionError, InvalidVolumeParameterError, MountOperationError):
                sys.exit(1)

        else:
            handleInvalidCommand()

    elif action in ("prepopulate"):
        # Get desired target from command line args
        target = getTarget(sys.argv)

        # Invoke desired action based on target
        if target in ("flexcache", "cache"):
            volumeName = None
            paths = None

            # Get command line options
            try:
                opts, args = getopt.getopt(sys.argv[3:], "hn:p:", ["help", "name=", "paths="])
            except:
                handleInvalidCommand(helpText=helpTextPrepopulateFlexCache, invalidOptArg=True)

            # Parse command line options
            for opt, arg in opts:
                if opt in ("-h", "--help"):
                    print(helpTextPrepopulateFlexCache)
                    sys.exit(0)
                elif opt in ("-n", "--name"):
                    volumeName = arg
                elif opt in ("-p", "--paths"):
                    paths = arg

            # Check for required options
            if not volumeName or not paths :
                handleInvalidCommand(helpText=helpTextPrepopulateFlexCache, invalidOptArg=True)

            # Convert paths string to list
            pathsList = paths.split(",")

            # Prepopulate FlexCache
            try:
                prepopulate_flex_cache(volume_name=volumeName, paths=pathsList, print_output=True)
            except (InvalidConfigError, APIConnectionError, InvalidVolumeParameterError):
                sys.exit(1)

        else:
            handleInvalidCommand()

    elif action in ("pull-from-s3", "pull-s3", "s3-pull"):
        # Get desired target from command line args
        target = getTarget(sys.argv)

        # Invoke desired action based on target
        if target in ("bucket"):
            s3Bucket = None
            s3ObjectKeyPrefix = ""
            localDirectory = None

            # Get command line options
            try:
                opts, args = getopt.getopt(sys.argv[3:], "hb:p:d:e:", ["help", "bucket=", "key-prefix=", "directory="])
            except:
                handleInvalidCommand(helpText=helpTextPullFromS3Bucket, invalidOptArg=True)

            # Parse command line options
            for opt, arg in opts:
                if opt in ("-h", "--help") :
                    print(helpTextPullFromS3Bucket)
                    sys.exit(0)
                elif opt in ("-b", "--bucket"):
                    s3Bucket = arg
                elif opt in ("-p", "--key-prefix"):
                    s3ObjectKeyPrefix = arg
                elif opt in ("-d", "--directory"):
                    localDirectory = arg

            # Check for required options
            if not s3Bucket or not localDirectory:
                handleInvalidCommand(helpText=helpTextPullFromS3Bucket, invalidOptArg=True)

            # Push file to S3
            try:
                pull_bucket_from_s3(s3_bucket=s3Bucket, local_directory=localDirectory, s3_object_key_prefix=s3ObjectKeyPrefix, print_output=True)
            except (InvalidConfigError, APIConnectionError):
                sys.exit(1)

        elif target in ("object", "file"):
            s3Bucket = None
            s3ObjectKey = None
            localFile = None

            # Get command line options
            try:
                opts, args = getopt.getopt(sys.argv[3:], "hb:k:f:", ["help", "bucket=", "key=", "file=", "extra-args="])
            except:
                handleInvalidCommand(helpText=helpTextPullFromS3Object, invalidOptArg=True)

            # Parse command line options
            for opt, arg in opts:
                if opt in ("-h", "--help"):
                    print(helpTextPullFromS3Object)
                    sys.exit(0)
                elif opt in ("-b", "--bucket"):
                    s3Bucket = arg
                elif opt in ("-k", "--key"):
                    s3ObjectKey = arg
                elif opt in ("-f", "--file"):
                    localFile = arg

            # Check for required options
            if not s3Bucket or not s3ObjectKey:
                handleInvalidCommand(helpText=helpTextPullFromS3Object, invalidOptArg=True)

            # Push file to S3
            try:
                pull_object_from_s3(s3_bucket=s3Bucket, s3_object_key=s3ObjectKey, local_file=localFile, print_output=True)
            except (InvalidConfigError, APIConnectionError):
                sys.exit(1)

        else:
            handleInvalidCommand()

    elif action in ("push-to-s3", "push-s3", "s3-push"):
        # Get desired target from command line args
        target = getTarget(sys.argv)

        # Invoke desired action based on target
        if target in ("directory", "dir"):
            s3Bucket = None
            s3ObjectKeyPrefix = ""
            localDirectory = None
            s3ExtraArgs = None

            # Get command line options
            try:
                opts, args = getopt.getopt(sys.argv[3:], "hb:p:d:e:", ["help", "bucket=", "key-prefix=", "directory=", "extra-args="])
            except:
                handleInvalidCommand(helpText=helpTextPushToS3Directory, invalidOptArg=True)

            # Parse command line options
            for opt, arg in opts:
                if opt in ("-h", "--help") :
                    print(helpTextPushToS3Directory)
                    sys.exit(0)
                elif opt in ("-b", "--bucket"):
                    s3Bucket = arg
                elif opt in ("-p", "--key-prefix"):
                    s3ObjectKeyPrefix = arg
                elif opt in ("-d", "--directory"):
                    localDirectory = arg
                elif opt in ("-e", "--extra-args"):
                    s3ExtraArgs = arg

            # Check for required options
            if not s3Bucket or not localDirectory:
                handleInvalidCommand(helpText=helpTextPushToS3Directory, invalidOptArg=True)

            # Push file to S3
            try:
                push_directory_to_s3(s3_bucket=s3Bucket, local_directory=localDirectory, s3_object_key_prefix=s3ObjectKeyPrefix, s3_extra_args=s3ExtraArgs, print_output=True)
            except (InvalidConfigError, APIConnectionError):
                sys.exit(1)

        elif target in ("file"):
            s3Bucket = None
            s3ObjectKey = None
            localFile = None
            s3ExtraArgs = None

            # Get command line options
            try:
                opts, args = getopt.getopt(sys.argv[3:], "hb:k:f:e:", ["help", "bucket=", "key=", "file=", "extra-args="])
            except:
                handleInvalidCommand(helpText=helpTextPushToS3File, invalidOptArg=True)

            # Parse command line options
            for opt, arg in opts:
                if opt in ("-h", "--help"):
                    print(helpTextPushToS3File)
                    sys.exit(0)
                elif opt in ("-b", "--bucket"):
                    s3Bucket = arg
                elif opt in ("-k", "--key"):
                    s3ObjectKey = arg
                elif opt in ("-f", "--file"):
                    localFile = arg
                elif opt in ("-e", "--extra-args"):
                    s3ExtraArgs = arg

            # Check for required options
            if not s3Bucket or not localFile:
                handleInvalidCommand(helpText=helpTextPushToS3File, invalidOptArg=True)

            # Push file to S3
            try:
                push_file_to_s3(s3_bucket=s3Bucket, s3_object_key=s3ObjectKey, local_file=localFile, s3_extra_args=s3ExtraArgs, print_output=True)
            except (InvalidConfigError, APIConnectionError):
                sys.exit(1)

        else:
            handleInvalidCommand()

    elif action in ("restore"):
        # Get desired target from command line args
        target = getTarget(sys.argv)

        # Invoke desired action based on target
        if target in ("snapshot", "snap"):
            volumeName = None
            snapshotName = None
            force = False

            # Get command line options
            try:
                opts, args = getopt.getopt(sys.argv[3:], "hn:v:f", ["help", "name=", "volume=", "force"])
            except:
                handleInvalidCommand(helpText=helpTextRestoreSnapshot, invalidOptArg=True)

            # Parse command line options
            for opt, arg in opts:
                if opt in ("-h", "--help"):
                    print(helpTextRestoreSnapshot)
                    sys.exit(0)
                elif opt in ("-n", "--name"):
                    snapshotName = arg
                elif opt in ("-v", "--volume"):
                    volumeName = arg
                elif opt in ("-f", "--force"):
                    force = True

            # Check for required options
            if not volumeName or not snapshotName:
                handleInvalidCommand(helpText=helpTextRestoreSnapshot, invalidOptArg=True)

            # Confirm restore operation
            if not force:
                print("Warning: When you restore a snapshot, all subsequent snapshots are deleted.")
                while True:
                    proceed = input("Are you sure that you want to proceed? (yes/no): ")
                    if proceed in ("yes", "Yes", "YES"):
                        break
                    elif proceed in ("no", "No", "NO"):
                        sys.exit(0)
                    else:
                        print("Invalid value. Must enter 'yes' or 'no'.")

            # Restore snapshot
            try:
                restore_snapshot(volume_name=volumeName, snapshot_name=snapshotName, print_output=True)
            except (InvalidConfigError, APIConnectionError, InvalidSnapshotParameterError, InvalidVolumeParameterError):
                sys.exit(1)

        else:
            handleInvalidCommand()

    elif action == "sync":
        # Get desired target from command line args
        target = getTarget(sys.argv)

        # Invoke desired action based on target
        if target in ("cloud-sync-relationship", "cloud-sync"):
            relationshipID = None
            waitUntilComplete = False

            # Get command line options
            try:
                opts, args = getopt.getopt(sys.argv[3:], "hi:w", ["help", "id=", "wait"])
            except:
                handleInvalidCommand(helpText=helpTextSyncCloudSyncRelationship, invalidOptArg=True)

            # Parse command line options
            for opt, arg in opts:
                if opt in ("-h", "--help"):
                    print(helpTextSyncCloudSyncRelationship)
                    sys.exit(0)
                elif opt in ("-i", "--id"):
                    relationshipID = arg
                elif opt in ("-w", "--wait"):
                    waitUntilComplete = True

            # Check for required options
            if not relationshipID:
                handleInvalidCommand(helpText=helpTextSyncCloudSyncRelationship, invalidOptArg=True)

            # Update cloud sync relationship
            try:
                sync_cloud_sync_relationship(relationship_id=relationshipID, wait_until_complete=waitUntilComplete, print_output=True)
            except (InvalidConfigError, APIConnectionError, CloudSyncSyncOperationError):
                sys.exit(1)

        elif target in ("snapmirror-relationship", "snapmirror"):
            uuid = None
            waitUntilComplete = False

            # Get command line options
            try:
                opts, args = getopt.getopt(sys.argv[3:], "hi:w", ["help", "uuid=", "wait"])
            except:
                handleInvalidCommand(helpText=helpTextSyncSnapMirrorRelationship, invalidOptArg=True)

            # Parse command line options
            for opt, arg in opts:
                if opt in ("-h", "--help"):
                    print(helpTextSyncSnapMirrorRelationship)
                    sys.exit(0)
                elif opt in ("-i", "--uuid"):
                    uuid = arg
                elif opt in ("-w", "--wait"):
                    waitUntilComplete = True

            # Check for required options
            if not uuid:
                handleInvalidCommand(helpText=helpTextSyncSnapMirrorRelationship, invalidOptArg=True)

            # Update SnapMirror relationship
            try:
                sync_snap_mirror_relationship(uuid=uuid, wait_until_complete=waitUntilComplete, print_output=True)
            except (
                    InvalidConfigError, APIConnectionError, InvalidSnapMirrorParameterError,
                    SnapMirrorSyncOperationError) :
                sys.exit(1)

        else:
            handleInvalidCommand()

    elif action in ("version", "v", "-v", "--version"):
        print("NetApp DataOps Toolkit for Traditional Environments - version "
              + traditional.__version__)

    else:
        handleInvalidCommand()