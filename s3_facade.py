# file_upload.py

import boto3
import os
from dotenv import load_dotenv
from logger import configured_logger
from botocore.exceptions import NoCredentialsError, ClientError

load_dotenv()


class S3Facade:
    def __init__(self):
        # Print out environment variable loading for debugging
        print("Environment Variables:")
        print(f"AWS_ACCESS_KEY_ID: {bool(os.getenv('AWS_ACCESS_KEY_ID'))}")
        print(f"AWS_SECRET_ACCESS_KEY: {bool(os.getenv('AWS_SECRET_ACCESS_KEY'))}")
        print(f"AWS_REGION: {os.getenv('AWS_REGION')}")
        print(f"S3_FORM_BUCKET: {os.getenv('S3_FORM_BUCKET')}")

        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_region = os.getenv("AWS_REGION")
        self.form_pdf_bucket_name = os.getenv("S3_FORM_BUCKET")
        self.data_schema_bucket_name = os.getenv("S3_DATA_SCHEMA_BUCKET")

        # Add additional validation
        if not all([self.aws_access_key_id, self.aws_secret_access_key, self.aws_region, self.form_pdf_bucket_name]):
            raise ValueError("Missing required AWS configuration. Check your environment variables.")

        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_region,
        )

    def upload_pdf_form(self, file_content: bytes, file_name: str) -> str:
        """
        Uploads a pdf form to the specified S3 bucket and returns the URL of the uploaded file.

        Args:
            file_content (bytes): The content of the file to upload.
            file_name (str): The name of the file to upload.

        Returns:
            str: The URL of the uploaded file in S3.
        """
        # Add extensive logging and validation
        configured_logger.info(f"Attempting to upload file: {file_name}")
        configured_logger.info(f"Bucket name from environment: '{self.form_pdf_bucket_name}'")
        configured_logger.info(f"AWS Access Key ID: '{bool(self.aws_access_key_id)}'")
        configured_logger.info(f"AWS Region: '{self.aws_region}'")

        # Explicit validation of critical parameters
        if not self.form_pdf_bucket_name:
            error_msg = "S3 bucket name is not set. Check your .env file and S3_FORM_BUCKET variable."
            configured_logger.error(error_msg)
            raise ValueError(error_msg)

        if not self.aws_access_key_id or not self.aws_secret_access_key:
            error_msg = "AWS credentials are missing. Check your .env file."
            configured_logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            # Explicitly pass all parameters
            self.s3.put_object(
                Bucket=str(self.form_pdf_bucket_name),  # Ensure it's a string
                Key=file_name,
                Body=file_content
            )

            file_url = f"https://{self.form_pdf_bucket_name}.s3.{self.aws_region}.amazonaws.com/{file_name}"
            configured_logger.debug(f"File uploaded to S3: {file_url}")
            return file_url
        except Exception as e:
            configured_logger.error(f"Detailed S3 upload error for {file_name}: {type(e).__name__} - {str(e)}")
            # Print out the full traceback for more detailed debugging
            import traceback
            traceback.print_exc()
            raise Exception(f"Could not upload file to S3: {str(e)}") from e

    def upload_schema(self, file_name: str) -> str:
        """
        Uploads a schema file to the specified S3 bucket and returns the URL of the uploaded file.

        Args:
            file_name (str): The name of the file to upload.

        Returns:
            str: The URL of the uploaded schema in S3.
        """
        try:
            # Read the schema file as a byte stream
            with open("schema.json", "rb") as f:
                byte_content = f.read()

            self.s3.put_object(
                Bucket=self.data_schema_bucket_name, Key=file_name, Body=byte_content,    ContentType='application/json'
            )

            file_url = f"https://{self.data_schema_bucket_name}.s3.{self.aws_region}.amazonaws.com/{file_name}"
            configured_logger.debug(f"Schema uploaded to S3: {file_url}")
            return file_url
        except (NoCredentialsError, ClientError) as e:
            configured_logger.error(f"S3 upload error, {file_name}: {e}")
            raise Exception("Could not upload schema to S3.") from e

    def download_schema(self, file_name: str):
        try:
            # Download the file from S3
            response = self.s3.get_object(Bucket=self.data_schema_bucket_name, Key=file_name)

            # Log successful download
            configured_logger.debug(
                f"Data schema '{file_name}' downloaded successfully from S3 bucket '{self.data_schema_bucket_name}'.")

            # Return the content of the file
            return response['Body'].read()

        except NoCredentialsError as e:
            configured_logger.error(
                f"S3 download error: Missing credentials when downloading '{file_name}' from bucket '{self.data_schema_bucket_name}': {e}")
            raise Exception(f"Missing credentials for S3 download of '{file_name}'.") from e

        except ClientError as e:
            configured_logger.error(
                f"S3 download error: Client error when downloading '{file_name}' from bucket '{self.data_schema_bucket_name}': {e}")
            raise Exception(f"Client error during S3 download of '{file_name}'.") from e

        except Exception as e:
            configured_logger.error(
                f"Unexpected error downloading '{file_name}' from S3 bucket '{self.data_schema_bucket_name}': {e}")
            raise Exception(f"Unexpected error during S3 download of '{file_name}'.") from e


s3 = S3Facade()
