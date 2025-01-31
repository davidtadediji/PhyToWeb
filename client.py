import gradio as gr
import requests
import json


def extract_text_data(file):
    """
    Extract data from uploaded resume using the existing API endpoint
    """
    if file is None:
        return {"error": "No file uploaded"}

    try:
        # Prepare multipart/form-data payload
        with open(file.name, 'rb') as f:
            files = {'file': f}
            form_data = {
                'data_schema_key': 'company_registration',
                'case_type': 'registration',
                'case_sub_type': 'company',
                'user_id': 'current_user'
            }

            # Make API call to extract endpoint
            response = requests.post('http://localhost:8002/api/extract/',
                                     files=files,
                                     data=form_data)

            # Check if request was successful
            response.raise_for_status()

            # Parse JSON response
            response_json = response.json()

            # Return the extracted form data or a descriptive error
            extracted_data = response_json.get('extracted_form_data', {})

            return extracted_data if extracted_data else {"error": "No data extracted"}

    except requests.RequestException as e:
        return {"error": f"API Request Error: {str(e)}"}
    except json.JSONDecodeError:
        return {"error": "Invalid JSON response from server"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


# Create Gradio interface
def data_analyzer_interface():
    interface = gr.Interface(
        fn=extract_text_data,
        inputs=gr.File(type="filepath", label="Upload Document (PDF/Image)"),
        outputs=gr.JSON(label="Extracted Form Data"),
        title="SilTextBridge",
        description="Upload a document to extract structured data"
    )
    return interface


# Launch the interface
if __name__ == "__main__":
    demo = data_analyzer_interface()
    demo.launch()