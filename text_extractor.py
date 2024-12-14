import boto3
import os
from dotenv import load_dotenv
from logger import configured_logger
from botocore.exceptions import NoCredentialsError, ClientError

# Load environment variables from .env
load_dotenv()

# Fetch credentials and region from environment
aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
aws_region = os.getenv('AWS_REGION')
bucket_name = os.getenv('S3_BUCKET')

print(aws_region, aws_secret_access_key, aws_access_key_id, bucket_name)

# Initialize S3 and Textract clients
s3 = boto3.client(
    's3',
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_region
)

textract = boto3.client(
    'textract',
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_region
)


def upload_file(file_content: bytes, file_name: str) -> str:
    """
    Uploads a file to the specified S3 bucket and returns the URL of the uploaded file.

    Args:
        file_content (bytes): The content of the file to upload.
        file_name (str): The name of the file to upload.

    Returns:
        str: The URL of the uploaded file in S3.
    """
    try:
        s3.put_object(
            Bucket=bucket_name, Key=file_name, Body=file_content
        )
        file_url = f"https://{bucket_name}.s3.{aws_region}.amazonaws.com/{file_name}"
        configured_logger.debug(f"File uploaded to S3: {file_url}")
        return file_url
    except (NoCredentialsError, ClientError) as e:
        configured_logger.error(f"S3 upload error: {e}")
        raise Exception("Could not upload file to S3.") from e


def text_extractor(s3_file_name: str) -> dict:
    """
    Extracts text from a document using AWS Textract.

    Args:
        s3_file_name (str): The S3 file name (path) of the document to analyze.

    Returns:
        dict: The response from AWS Textract containing the extracted data.
    """
    try:
        response = textract.analyze_document(
            Document={'S3Object': {'Bucket': bucket_name, 'Name': s3_file_name}},
            FeatureTypes=['TABLES', 'FORMS']
        )
        return response
    except (NoCredentialsError, ClientError) as e:
        configured_logger.error(f"Textract error: {e}")
        raise Exception("Could not extract text using Textract.") from e


def ensure_bucket_exists():
    """
    Checks if the specified S3 bucket exists. If not, creates it.
    """
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f'Bucket "{bucket_name}" already exists.')
    except s3.exceptions.ClientError as e:
        # If the bucket does not exist, create it
        if e.response['Error']['Code'] == 'NoSuchBucket':
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': aws_region}
            )
            print(f'Bucket "{bucket_name}" created.')
        else:
            raise  # Re-raise the error if it is another type of exception


def process_file(file_content: bytes, file_name: str):
    """
    Process the uploaded file by ensuring the bucket exists, uploading the file,
    and extracting text from it using Textract.
    """
    # Ensure the bucket exists (only when this function is called)
    ensure_bucket_exists()

    # Upload the file to S3
    file_url = upload_file(file_content, file_name)

    # Extract text from the uploaded file using Textract
    textract_response = text_extractor(file_name)

    # Print or process the Textract response
    print(textract_response)


# Example usage
with open("case_registration_form.pdf", "rb") as f:
    file_content = f.read()
    process_file(file_content, "case_registration_form.pdf")
