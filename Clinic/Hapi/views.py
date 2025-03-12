import requests
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate, logout
from .forms import UserRegistrationForm, DoctorRegistrationForm, PatientRegistrationForm, LoginForm
from .fhir_utils import create_practitioner_in_fhir, create_patient_in_fhir, get_fhir_data  # Import the functions
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from datetime import datetime, timedelta
import base64

FHIR_SERVER_URL = 'http://localhost:8080/fhir/'

# Create the view for the landing page
def landing_page(request):
    return render(request, 'landing_page.html')

# View for registering a new user (Doctor or Patient)
def register(request, role):
    if request.method == 'POST':
        user_form = UserRegistrationForm(request.POST)
        print(user_form.errors, "User Form")
        if user_form.is_valid():
            user = user_form.save(commit=False)
            user.role = role  # Assign role before saving
            user.username = user.email
            #user.save()  # Save CustomUser instance first

            # Handle Doctor registration
            if role == 'doctor':
                doctor_form = DoctorRegistrationForm(request.POST)
                print(doctor_form.errors, "doctror")
                if doctor_form.is_valid():
                    doctor = doctor_form.cleaned_data  # Extract cleaned data
                    fhir_id = create_practitioner_in_fhir(doctor)  # Pass dict, handle in function
                    print(fhir_id)
                    if fhir_id:
                        user.fhir_id = fhir_id  # Save the FHIR ID to CustomUser
                        user.save()
                    login(request, user)
                    messages.success(request, f"Welcome, {user.email}!")
                    return redirect('Hapi:dashboard')  # Redirect to user_dashboard or home page

            # Handle Patient registration
            elif role == 'patient':
                patient_form = PatientRegistrationForm(request.POST)
                print(patient_form.errors, "patient")
                if patient_form.is_valid():
                    patient = patient_form.cleaned_data  # Extract cleaned data
                    fhir_id = create_patient_in_fhir(patient)  # Pass dict, handle in function
                    print(fhir_id)
                    if fhir_id:
                        user.fhir_id = fhir_id  # Save the FHIR ID to CustomUser
                        user.save()
                    login(request, user)
                    messages.success(request, f"Welcome, {user.email}!")
                    return redirect('Hapi:dashboard')  # Redirect to user_dashboard or home page

        # If form is invalid, re-render with errors
        return render(request, 'register.html', {
            'role': role,
            'user_form': user_form,
            'doctor_form': DoctorRegistrationForm() if role == 'doctor' else None,
            'patient_form': PatientRegistrationForm() if role == 'patient' else None
        })
    
    else:
        user_form = UserRegistrationForm()
        doctor_form = DoctorRegistrationForm() if role == 'doctor' else None
        patient_form = PatientRegistrationForm() if role == 'patient' else None
        
        return render(request, 'register.html', {
            'role': role,
            'user_form': user_form,
            'doctor_form': doctor_form,
            'patient_form': patient_form
        })

def user_login(request):
    if request.user.is_authenticated:
        print("Yeap")
        return redirect('Hapi:dashboard')
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]
            
            user = authenticate(request, username=email, password=password)  # Use email as username
            
            if user is not None:
                login(request, user)
                print("Logg")
                messages.success(request, f"Welcome, {user.email}!")
                return redirect('Hapi:dashboard')  # Redirect to user_dashboard or home page
            else:
                messages.error(request, "Invalid email or password.")
    
    else:
        form = LoginForm()
    
    return render(request, "login.html", {"form": form})

def user_logout(request):
    # Log the user out
    logout(request)
    
    # Redirect to the login page or a landing page after logout
    return redirect('Hapi:login')  # You can change this to your desired page

@login_required
def user_dashboard(request):
    user = request.user
    fhir_id = user.fhir_id  
    
    fhir_data = get_fhir_data(fhir_id, user.role)
    if fhir_data:
        if user.role == 'doctor':
            # Fetch Pending Appointments
            print(fhir_id)
            pending_appointments = requests.get(f"{FHIR_SERVER_URL}/Appointment?actor=Practitioner/{user.fhir_id}&status=proposed")
            print(pending_appointments.status_code)
            if pending_appointments.status_code == 200:
                appointments = pending_appointments.json().get("entry", [])
            else:
                appointments = []
            print(appointments)
            return render(request, 'doctor_dashboard.html', {'fhir_data': fhir_data, 'pending_appointments': appointments})
        else:
            return render(request, 'patient_dashboard.html', {'fhir_data': fhir_data, 'user':user})
    else:
        return render(request, 'dashboard.html', {'error': 'No FHIR data found.'})

@login_required
def doctor_profile(request):
    user = request.user
    fhir_id = user.fhir_id
    fhir_data = get_fhir_data(fhir_id, user.role)
    if request.method == 'POST':
        # Extract data from the form
        data = request.POST

        files = request.FILES
        profile_picture = files.get('profile_picture')
        photo_data = None
        if profile_picture:
            photo_data = base64.b64encode(profile_picture.read()).decode('utf-8')
        else:
            if 'photo' in fhir_data and fhir_data['photo']:
                photo_data = fhir_data['photo'][0]['data']
        # Handle multiple specializations
        specializations = data.getlist('specialization[]')

        # Handle multiple education entries
        degrees = data.getlist('degree[]')
        colleges = data.getlist('college[]')
        years_of_completion = data.getlist('yearOfCompletion[]')

        # Handle multiple experience entries
        hospitals = data.getlist('hospital[]')
        designations = data.getlist('designation[]')
        exp_from = data.getlist('expFrom[]')
        exp_to = data.getlist('expTo[]')

        # Prepare the updated Practitioner resource
        updated_practitioner = {
            "resourceType": "Practitioner",
            "id": fhir_id,  # Use the stored FHIR ID
            "name": [{
                "use": "official",
                "family": data.get('lastName', ''),
                "given": [data.get('firstName', '')],
            }],
            "gender": data.get('gender', ''),
            "birthDate": data.get('dob', ''),
            "telecom": [{"system": "phone", "value": data.get('phone', '')}],
            "address": [{
                "line": [data.get('address1', ''), data.get('address2', '')],
                "city": data.get('city', ''),
                "state": data.get('state', ''),
                "postalCode": data.get('postalCode', ''),
                "country": data.get('country', '')
            }],
            "qualification": [
                {
                    "code": {"text": degrees[i]},
                    "issuer": {"display": colleges[i]},
                    "period": {"end": years_of_completion[i]}
                }
                for i in range(len(degrees))  # Loop through all education entries
            ],
            "photo": [{
                "contentType": profile_picture.content_type if profile_picture else fhir_data['photo'][0]['contentType'],
                "data": photo_data,
                "title": "Profile Picture"
            }] if profile_picture else None
        }

        # Send the updated Practitioner resource to the HAPI FHIR server
        hapi_fhir_url = f"{FHIR_SERVER_URL}Practitioner/{fhir_id}"
        response = requests.put(hapi_fhir_url, json=updated_practitioner)
        if response.status_code != 200:
            # Handle errors (e.g., display an error message)
            return render(request, 'doctor_profile.html', {
                'error': 'Failed to update Practitioner profile',
                "fhir_data": fhir_data,
                "user": user
            })

        # Fetch the PractitionerRole resource using the Practitioner FHIR ID
        practitioner_role_url = f"{FHIR_SERVER_URL}PractitionerRole?practitioner={fhir_id}"
        practitioner_role_response = requests.get(practitioner_role_url)
        if practitioner_role_response.status_code == 200:
            practitioner_role_data = practitioner_role_response.json()
            if practitioner_role_data.get('total', 0) > 0:
                # Assuming the first role is the one to update
                practitioner_role = practitioner_role_data['entry'][0]['resource']
                practitioner_role_id = practitioner_role['id']
            else:
                # If no PractitionerRole exists, create a new one
                practitioner_role_id = None
        else:
            return render(request, 'doctor_profile.html', {
                'error': 'Failed to fetch PractitionerRole',
                "fhir_data": fhir_data,
                "user": user
            })

        # Prepare the updated PractitionerRole resource
        updated_practitioner_role = {
            "resourceType": "PractitionerRole",
            "practitioner": {"reference": f"{FHIR_SERVER_URL}Practitioner/{fhir_id}"},
            "organization": {"display": data.get('clinicName', '')},
            "location": [{"display": data.get('clinicAddress', '')}],
            "specialty": [{"text": spec} for spec in specializations],  # Add all specializations
            "extension": [
                {
                    "url": "http://example.org/StructureDefinition/experience",
                    "valueString": hospitals[i],
                    "period": {
                        "start": exp_from[i],
                        "end": exp_to[i]
                    }
                }
                for i in range(len(hospitals))  # Loop through all experience entries
            ]
        }

        # Update or create the PractitionerRole resource
        if practitioner_role_id:
            # Update existing PractitionerRole
            updated_practitioner_role["id"] = practitioner_role_id
            practitioner_role_url = f"{FHIR_SERVER_URL}PractitionerRole/{practitioner_role_id}"
            role_response = requests.put(practitioner_role_url, json=updated_practitioner_role)
        else:
            # Create new PractitionerRole
            practitioner_role_url = f"{FHIR_SERVER_URL}PractitionerRole"
            role_response = requests.post(practitioner_role_url, json=updated_practitioner_role)

        if role_response.status_code in [200, 201]:
            # Redirect to the dashboard with a success message
            return redirect('Hapi:dashboard')
        else:
            # Handle errors (e.g., display an error message)
            return render(request, 'doctor_profile.html', {
                'error': 'Failed to update PractitionerRole',
                "fhir_data": fhir_data,
                "user": user
            })

    # Render the profile page with FHIR data
    return render(request, 'doctor_profile.html', {
        "fhir_data": fhir_data,
        "user": user
    })

@login_required
def doctor_list(request):
    response = requests.get(f"{FHIR_SERVER_URL}/Practitioner")
    doctors = []
    if response.status_code == 200:
        doctors = response.json().get("entry", [])
    return render(request, 'doctors_list.html', {'doctors': doctors})
    
# Appointment Management
@login_required
def request_appointment(request):
    if request.method == 'POST':
        # Get data from the request
        patient_id = request.POST.get('patient_id')
        doctor_id = request.POST.get('doctor_id')
        date_time_str = request.POST.get('date_time')  # Assuming this is in ISO format
        reason = request.POST.get('reason')

        # Convert the date_time string to a datetime object
        date_time = datetime.fromisoformat(date_time_str)

        # Calculate the end time (30 minutes later)
        end_time = date_time + timedelta(minutes=30)

        # Create an Appointment resource
        appointment = {
            "resourceType": "Appointment",
            "status": "proposed",
            "participant": [
                {
                    "actor": {
                        "reference": f"Patient/{patient_id}"
                    },
                    "status": "accepted"
                },
                {
                    "actor": {
                        "reference": f"Practitioner/{doctor_id}"
                    },
                    "status": "needs-action"
                }
            ],
            "start": date_time.isoformat(),
            "end": end_time.isoformat(),
            "description": reason
        }

        # Post the Appointment resource to the FHIR server
        
        res = requests.post(f"{FHIR_SERVER_URL}/Appointment", json=appointment)
        if res.status_code == 200:
            appointments = res.json().get('entry', [])
            return render(request, "doctor_appoinment.html")
        else:
            return JsonResponse({'error': 'Failed to fetch appointments', 'details': res.text}, status=400)
    return render(request, "doctor_appoinment.html")
    
@login_required
def pending_appointments(request):
    user = request.user
    response = requests.get(f"{FHIR_SERVER_URL}/Appointment?participant=Practitioner/{user.fhir_id}&status=proposed")

    if response.status_code == 200:
        appointments = response.json().get("entry", [])
    else:
        appointments = []

    return render(request, "pending_appointments.html", {"appointments": appointments, "doctor_id": user.fhir_id})

@login_required
def update_appointment_status(request, appointment_id, action):
    new_status = "booked" if action == "accept" else "cancelled"

    response = requests.get(f"{FHIR_SERVER_URL}/Appointment/{appointment_id}")
    if response.status_code != 200:
        return HttpResponse("Appointment not found.", status=404)

    appointment_data = response.json()
    appointment_data["status"] = new_status

    update_response = requests.put(f"{FHIR_SERVER_URL}/Appointment/{appointment_id}", json=appointment_data)

    if update_response.status_code == 200:
        return redirect(request.META.get("HTTP_REFERER", "/"))  # Redirect back to the previous page
    else:
        return HttpResponse("Failed to update appointment.", status=400)

