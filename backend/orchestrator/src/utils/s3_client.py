import boto3
from botocore.exceptions import ClientError
import logging
import os

class S3Client:
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=os.environ.get('AWS_REGION')
        )
        self.bucket_name = os.environ.get('AWS_S3_BUCKET')

    def upload_file(self, file_path, object_name=None):
        """Upload a file to S3 bucket

        :param file_path: File to upload
        :param object_name: S3 object name. If not specified original filename is used
        :return: True if file was uploaded, else False
        """
        if object_name is None:
            object_name = os.path.basename(file_path)

        try:
            self.s3.upload_file(file_path, self.bucket_name, object_name)
            logging.info(f"Successfully uploaded {file_path} to {self.bucket_name}/{object_name}")
            return True
        except ClientError as e:
            logging.error(f"Error uploading file to S3: {e}")
            return False

    def download_file(self, object_name, file_path):
        """Download a file from S3 bucket

        :param object_name: S3 object name
        :param file_path: Local path to save file
        :return: True if file was downloaded, else False
        """
        try:
            self.s3.download_file(self.bucket_name, object_name, file_path)
            logging.info(f"Successfully downloaded {self.bucket_name}/{object_name} to {file_path}")
            return True
        except ClientError as e:
            logging.error(f"Error downloading file from S3: {e}")
            return False