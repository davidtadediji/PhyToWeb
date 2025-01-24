import json
from datetime import datetime
from pydantic import BaseModel, ValidationError
import hashlib
import re
import os

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, BaseModel):
            return obj.model_dump()
        return super().default(obj)


def get_file_hash(file_content: bytes) -> str:
    """
    Computes the SHA-256 hash of the file content.
    """
    return hashlib.sha256(file_content).hexdigest()


ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.jpg', '.jpeg', '.png'}

def is_valid_filename(file_name: str) -> bool:
    """
    Validate the filename to ensure it meets specific criteria.

    Args:
        file_name (str): The file name to validate.

    Returns:
        bool: True if the filename is valid, False otherwise.
    """
    # Check for valid file extension
    _, file_extension = os.path.splitext(file_name)
    if file_extension.lower() not in ALLOWED_EXTENSIONS:
        print(f"Invalid file extension: {file_extension}")
        return False

    # Check if the filename is too long (limit to 255 characters)
    if len(file_name) > 255:
        print("Filename is too long. Max length is 255 characters.")
        return False

    # Ensure the filename doesn't contain invalid characters
    # Allow letters, numbers, underscores, hyphens, and periods only
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', file_name):
        print(f"Invalid characters in filename: {file_name}")
        return False

    return True


def validate_output(data):
    """Validate the serialized output against expected structure"""
    if not isinstance(data, dict):
        raise ValidationError("Invalid output format: expected dictionary")