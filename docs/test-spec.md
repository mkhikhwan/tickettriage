# Test Specification: Ticket Triage Project

This document serves as the official Test Specification for the Ticket Triage project. It breaks down each step of the suggested system flow into granular positive and negative test cases to verify application behavior at every stage of execution.

---

### 1. User Opens the Ticket Triage Web Application

* **Action:** User navigates to the web application URL hosted on Azure Static Web Apps.
* **Expected Result:** The application loads successfully in the browser with all UI elements (ticket form, header, navigation) visible and responsive.
* **Result:** ✅ Success - Website can be opened from desktop and mobile.

---

### 2. User Submits a Support Request Through the Ticket Form

#### 2.a. Complete Data (Positive)
* **Data:** Name: "Aiman Rahman", Email: "aiman@example.com", Title: "Cannot access campus Wi-Fi", Description: "I cannot connect to the campus Wi-Fi from my laptop", Priority: "Medium".
* **Action:** Fill in all form fields with valid data and click the Submit button.
* **Expected Result:** The form passes client-side validation, submits successfully, displays a success confirmation message, and clears the input fields.
* **Result:** ✅ Success - Form is submitted successfully.

#### 2.b. Incomplete Data (Negative)
* **Data:** Name: "Aiman Rahman", Email: "aiman@example.com", Title: "", Description: "", Priority: "".
* **Action:** Leave required fields (Title and Description) blank and click the Submit button.
* **Expected Result:** Client-side validation triggers, preventing form submission. Clear error messages appear under the missing required fields.
* **Result:** ✅ Success - Form didn't submit.

#### 2.c. Invalid Data Format (Negative)
* **Data:** Name: "Aiman Rahman", Email: "aimanexample.com", Title: "Need help", Description: "Broken link", Priority: "Low".
* **Action:** Enter a malformed email address and click the Submit button.
* **Expected Result:** Form validation catches the invalid email format, displays an error message ("Please enter a valid email address"), and blocks submission.
* **Result:** ✅ Success - Form didn't submit.

---

### 3. Backend API Receives the Request

#### 3.a. Valid Request Payload (Positive)
* **Data:** Valid JSON payload containing ticket details sent to the Azure Functions API endpoint.
* **Action:** Send the request payload from the frontend to the backend API.
* **Expected Result:** The API returns a 200/201 Success status code, accepting the request for processing without CORS or authentication errors.
* **Result:** ✅ Success - API returns status 200.

#### 3.b. Malformed Request Payload (Negative)
* **Data:** Empty payload `{}` or missing JSON parameters sent directly to the API endpoint.
* **Action:** Trigger the API with missing required attributes.
* **Expected Result:** The backend API catches the invalid payload and returns a 400 Bad Request HTTP status code with an appropriate error message, without crashing.
* **Result:** ⚠️ Not Tested

---

### 4. System Suggests a Category Using Free-Tier AI or Keyword Logic

#### 4.a. Standard Categorization (Positive)
* **Data:** Description: "I cannot connect to the campus Wi-Fi from my laptop".
* **Action:** Backend passes description to Azure AI Language or keyword classification logic.
* **Expected Result:** The system accurately maps the input to the target category "IT Support".
* **Result:** ✅ Success - Ticket was categorized as "IT Support".

#### 4.b. Ambiguous / Unclear Input Handling (Negative / Edge Case)
* **Data:** Description: "asdfghjkl 12345" or "I need help with something general".
* **Action:** Backend passes ambiguous input to the classification service.
* **Expected Result:** The classification logic safely falls back to assigning a default category (e.g., "General Enquiry") instead of failing or throwing an exception.
* **Result:** ✅ Success - Ticket was categorized as "General Inquiry".

---

### 5. Ticket Is Saved in the Database with Status New or Categorised

#### 5.a. Successful Cosmos DB Persistence (Positive)
* **Data:** Categorized ticket payload with generated GUID, status "New", and creation timestamp.
* **Action:** Backend writes the ticket record into Azure Cosmos DB NoSQL container.
* **Expected Result:** Document persists in Azure Cosmos DB with an auto-generated unique ID, status set to "New", and accurate created date.
* **Result:** ✅ Success - Database saved the payload.

#### 5.b. Database Connection or Key Failure (Negative)
* **Data:** Valid ticket payload.
* **Action:** Backend attempts to write to Cosmos DB when connection credentials or network settings are incorrect/unreachable.
* **Expected Result:** API logs the error securely via Azure Key Vault / App monitoring and returns a 500 Internal Server Error message to the frontend without hanging indefinitely.
* **Result:** ✅ Success - System falls back to In-Memory.

---

### 6. Admin Opens the Ticket Review Page

#### 6.a. Dashboard Load & Data Retrieval (Positive)
* **Action:** Admin navigates to the ticket review dashboard page.
* **Expected Result:** The page queries the API and fetches all stored tickets from Azure Cosmos DB, presenting them in a clear list view.
* **Result:** ✅ Success - Admin page can be opened after entering admin key.

#### 6.b. Empty Database / Network Failure (Negative)
* **Action:** Admin opens the page when no tickets exist in the database or during API downtime.
* **Expected Result:** The UI gracefully displays an empty state ("No tickets found") or an error notification, rather than breaking the layout or displaying raw console errors.
* **Result:** ⚠️ Not Tested

---

### 7. Admin Reviews the Ticket and Updates the Status

#### 7.a. Valid Status Update (Positive)
* **Data:** Target Ticket ID, New Status: "In Progress" or "Resolved".
* **Action:** Admin selects a ticket from the list, updates its status dropdown to "In Progress", and saves.
* **Expected Result:** The backend API updates the document in Azure Cosmos DB, returns a 200 OK, and the dashboard UI reflects the new status immediately.
* **Result:** ✅ Success - Able to update status and keep the changes in the database and retrieve with status 200.

#### 7.b. Invalid Status Payload (Negative)
* **Data:** Target Ticket ID, Status: "" (empty or invalid string).
* **Action:** Attempt to send an invalid status payload to the update API.
* **Expected Result:** The API rejects the status update request with a 400 Bad Request code, leaving the existing status intact in Azure Cosmos DB.
* **Result:** ⚠️ Not Tested

---

### 8. Updated Ticket Remains Available for Tracking and Demo Purposes

#### 8.a. State Persistence Verification (Positive)
* **Action:** Refresh the browser page or navigate away and return to the Admin review dashboard.
* **Expected Result:** The updated ticket status ("In Progress" or "Resolved") persists in the database and renders correctly upon reload.
* **Result:** ✅ Success - Updated ticket remains in the database.