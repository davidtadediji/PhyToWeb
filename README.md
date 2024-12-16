# PhytoWeb

PhytoWeb is a powerful tool designed to automate the extraction of data from physical forms and seamlessly fill out
web-based forms. By leveraging Optical Character Recognition (OCR), data parsing technologies, and Large Language
Models (LLMs), PhytoWeb transforms paper-based information into digital form submissions, saving time and reducing
manual entry errors.

## Features

- **OCR-based Data Extraction**: Extracts text from physical forms using OCR technology.
- **Web Form Integration**: Automatically populates web forms with extracted data.
- **Customizable Fields**: Adaptable to various form structures and web platforms.
- **Error Detection**: Identifies and flags any inconsistencies or missing information.
- **User-Friendly Interface**: Simple setup and easy-to-use interface.
- **Schema Upload**: Supports dynamic schema upload to integrate custom form structures.
- **LLM-powered Form Processing**: Use advanced language models to process and format form data.

## Installation

### Requirements

- Python 3.7+
- pip (Python package installer)
- A modern web browser (for web form interaction)
- **Tesseract OCR** (for data extraction) - Follow the installation instructions based on your operating system.

### Dependencies

Install the required libraries using pip:

```bash
pip install -r requirements.txt
```

You will also need to install Tesseract OCR for data extraction. Follow the installation instructions based on your
operating system:

Windows: Tesseract Installation
Linux: Use sudo apt-get install tesseract-ocr (for Ubuntu/Debian)
macOS: Use brew install tesseract (for Homebrew users)
Setup
Clone the repository:

```bash
git clone https://github.com/yourusername/phytoweb.git
cd phytoweb
```

```bash
pip install -r requirements.txt
```

Set up the necessary configuration files (e.g., for web form fields) by editing config.json in the project directory.

## Usage

### Upload a Schema of the Data

To upload a form schema (a JSON object that defines the structure of the form fields), use the `/api/upload-schema`
endpoint.

**Example request:**

```bash
curl -X POST http://localhost:8000/api/upload-schema \
    -H "Content-Type: application/json" \
    -d '{
        "key": "unique_schema_key",
        "data_schema": {
            "field1": "string",
            "field2": "integer",
            "field3": "boolean"
        }
    }'
```

This will upload the schema with the key unique_schema_key.

### Extract Form Data

To extract data from an uploaded form, use the /api/extract/ endpoint. The service will process the form file (e.g., a
PDF) using AWS Textract and extract the relevant data based on the uploaded schema.

Example request:

```bash
curl -X POST http://localhost:8000/api/extract/ \
    -F "file=@path/to/your/form.pdf" \
    -F "data_schema_key=unique_schema_key" \
    -F "case_type=REGISTRATION" \
    -F "case_sub_type=NGO_REGISTRATION" \
    -F "user_id=user123" \
    -F "timestamp=2024-12-16"
```

The response will contain the extracted form data based on the schema.

Response Example:

```json
{
  "data_schema_key": "unique_schema_key",
  "case_type": "REGISTRATION",
  "case_sub_type": "NGO_REGISTRATION",
  "user_id": "user123",
  "timestamp": "2024-12-16T12:34:56+00:00",
  "form_text_data": "Extracted text from the form",
  "extracted_form_data": {
    "field1": "value1",
    "field2": 123,
    "field3": true
  }
}
```

The extracted_form_data will contain the data that can be used to autofill web forms.

Error Handling
If there is an error during processing (e.g., invalid schema or failed extraction), the service will return an error
message with a 500 status code.

Example error response:

```
{
    "error": "Failed to extract form data",
    "details": "Error message details"
}

```

This is the recommended way to integrate PhytoWeb with your application for automatic data extraction and form
population.

Let me know if any further adjustments are needed!

### Contact

For any questions or feedback, please open an issue in the repository or contact us at davidtadediji@gmail.com.