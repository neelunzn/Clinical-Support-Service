import requests

# HAPI FHIR server URL
FHIR_SERVER_URL = 'http://localhost:8080/fhir/'

# Function to create Practitioner resource in HAPI FHIR
def create_practitioner_in_fhir(doctor_data):
    practitioner_data = {
        "resourceType": "Practitioner",
        "name": [{
            "use": "official",
            "family": doctor_data["last_name"],
            "given": [doctor_data["first_name"]],
        }],
        "identifier": [{
            "use": "official",
            "system": "http://example.com/practitioners",
            "value": str(doctor_data["license_number"]),
        }],
        "gender": "male" if doctor_data["gender"] == 'M' else "female",
        "birthDate": str(doctor_data["date_of_birth"]),
        "telecom": [{
            "system": "phone",
            "value": doctor_data["phone"],
            "use": "mobile",
        }],
    }

    # POST the practitioner data to the HAPI FHIR server
    response = requests.post(f"{FHIR_SERVER_URL}Practitioner", json=practitioner_data)
    if response.status_code == 201:
        return response.json()['id']  # Return FHIR ID if successful
    else:
        print("Failed")
        return None  # Failed

# Function to create Patient resource in HAPI FHIR
def create_patient_in_fhir(patient_info):
    patient_data = {
        "resourceType": "Patient",
        "name": [{
            "use": "official",
            "family": patient_info["last_name"],
            "given": [patient_info["first_name"]],
        }],
        "gender": "male" if patient_info["gender"] == 'M' else "female",
        "birthDate": str(patient_info["date_of_birth"]),
        "address": [{
            "line": patient_info["address"],
            "city": "",
            "state": "",
            "postalCode": "",
        }],
        "telecom": [{
            "system": "phone",
            "value": patient_info["phone"],
            "use": "mobile",
        }],
    }

    # POST the patient data to the HAPI FHIR server
    response = requests.post(f"{FHIR_SERVER_URL}Patient", json=patient_data)
    if response.status_code == 201:
        return response.json()['id']  # Return FHIR ID if successful
    else:
        return None  # Failed

# Function to get data from FHIR server (for a doctor or patient)
def get_fhir_data(fhir_id, role):
    # Construct the URL for the FHIR resource (e.g., Practitioner or Patient)
    url = f"{FHIR_SERVER_URL}Patient/{fhir_id}"  # Adjust resource type as needed (Practitioner or Patient)
    if role == "doctor":
        url = f"{FHIR_SERVER_URL}Practitioner/{fhir_id}"  # Adjust resource type as needed (Practitioner or Patient)
    
    # Send a GET request to the FHIR server
    response = requests.get(url)
    
    # Check if the request was successful
    print(response.status_code)
    if response.status_code == 200:
        return response.json()  # Return the JSON data
    else:
        return None  # If the request failed, return None