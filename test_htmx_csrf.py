import requests

session = requests.Session()
login_url = "http://127.0.0.1:8000/login/"

# 1. Get CSRF cookie from login page
response1 = session.get(login_url)
csrftoken = session.cookies.get('csrftoken')
print(f"Got CSRF token from login page: {csrftoken is not None}")

# 2. Login
login_data = {
    'username': 'test@example.com',
    'password': 'testpassword123',
    'csrfmiddlewaretoken': csrftoken,
    'next': '/'
}
response2 = session.post(login_url, data=login_data, headers={'Referer': login_url})
print(f"Login response status: {response2.status_code} (Expect 200 or 302)")

# 3. Simulate HTMX POST request (e.g. changing order status or creating something)
# We will just hit an arbitrary POST endpoint that requires CSRF and login
# Let's try to logout via POST using the HTMX CSRF header
logout_url = "http://127.0.0.1:8000/logout/"
new_csrftoken = session.cookies.get('csrftoken') # Might have changed after login

htmx_headers = {
    'HX-Request': 'true',
    'X-CSRFToken': new_csrftoken,
    'Referer': 'http://127.0.0.1:8000/'
}

response3 = session.post(logout_url, headers=htmx_headers)
print(f"HTMX POST response status: {response3.status_code}")
if response3.status_code == 403:
    print("FAILED: CSRF validation failed for HTMX request. The fix might not be recognized by Django if only in base.html and we test via requests.")
elif response3.status_code in (200, 302):
    print("SUCCESS: The endpoint accepted the request with X-CSRFToken header!")
else:
    print(f"OTHER STATUS: {response3.status_code} - {response3.text[:100]}")

