import boto3
import os
from dotenv import load_dotenv
from logger import configured_logger
from botocore.exceptions import NoCredentialsError, ClientError

# Load environment variables from .env
load_dotenv()

# Fetch credentials and region from environment
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
aws_region = os.getenv("AWS_REGION")
bucket_name = os.getenv("S3_BUCKET")


# Initialize S3 and Textract clients
s3 = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_region,
)


# def upload_file(file_content: bytes, file_name: str) -> str:
#     """
#     Uploads a file to the specified S3 bucket and returns the URL of the uploaded file.
#
#     Args:
#         file_content (bytes): The content of the file to upload.
#         file_name (str): The name of the file to upload.
#
#     Returns:
#         str: The URL of the uploaded file in S3.
#     """
#     try:
#         s3.put_object(Bucket=bucket_name, Key=file_name, Body=file_content)
#         file_url = f"https://{bucket_name}.s3.{aws_region}.amazonaws.com/{file_name}"
#         configured_logger.debug(f"File uploaded to S3: {file_url}")
#         return file_url
#     except (NoCredentialsError, ClientError) as e:
#         configured_logger.error(f"S3 upload error: {e}")
#         raise Exception("Could not upload file to S3.") from e
