# Ticket Triage - AI Helpdesk Assistant

Welcome to the Ticket Triage project! This application is designed to receive support tickets from students and staff, classify them automatically using AI or keyword-matching logic, save them in Cosmos DB, and allow support admins to manage their lifecycle.

The application is configured to run fully on Azure Free-Tier services: **Static Web Apps**, **Managed Azure Functions (Python 3.11)**, **Cosmos DB for NoSQL**, and **Azure Key Vault**.

---

## Contents
1. [Prerequisites](#1-prerequisites)
2. [Local Setup & Installation](#2-local-setup--installation)
3. [Running the Application Locally](#3-running-the-application-locally)
4. [Connecting to Live Cosmos DB (Local Testing)](#4-connecting-to-live-cosmos-db-local-testing)
5. [Running Unit Tests](#5-running-unit-tests)
6. [Step-by-Step Azure Deployment Guide](#6-step-by-step-azure-deployment-guide)

---

## 1. Prerequisites

Before starting, ensure you have the following installed:
* **Git**
* **Python 3.11** or **Python 3.12**
* An active **Azure Account** (with student/free credits)

---

## 2. Local Setup & Installation

Follow these steps to set up your project environment:

### Step 1: Open the Terminal
Make sure you are in the target directory (without the hyphen):
```bash
cd tickettriage
```

### Step 2: Create a Virtual Environment
Create a localized Python environment:
```bash
python -m venv .venv
```

### Step 3: Activate the Virtual Environment
* **On Bash (Git Bash, WSL, Linux/macOS)**:
  ```bash
  source .venv/Scripts/activate
  ```
* **On PowerShell**:
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
* **On Command Prompt (CMD)**:
  ```cmd
  .venv\Scripts\activate.bat
  ```

### Step 4: Install Dependencies
Install all required libraries and testing tools:
```bash
pip install -r requirements-dev.txt
```

---

## 3. Running the Application Locally

The repository contains a zero-dependency development server (`dev_server.py`) that hosts the static frontend and resolves the API endpoints.

### Step 1: Start the Server
With your virtual environment active, run:
```bash
python scripts/dev_server.py
```

### Step 2: Open in Browser
* **Frontend Ticket Form**: [http://localhost:4280](http://localhost:4280)
* **Admin Dashboard**: [http://localhost:4280/admin](http://localhost:4280/admin)
* **API Health Check**: [http://localhost:4280/api/health](http://localhost:4280/api/health)

### Step 3: Seed Sample Data
Open a second terminal window, navigate to `tickettriage`, activate the virtual environment, and run:
```bash
python scripts/seed_api.py
```
This loads 18 mock tickets to test the category classification model accuracy.

---

## 4. Connecting to Live Cosmos DB (Local Testing)

By default, the application runs in **in-memory** mode. To test it with your actual live Cosmos DB container:

### Step 1: Retrieve your Cosmos DB Connection String
1. Log into the [Azure Portal](https://portal.azure.com/).
2. Select your Cosmos DB Account.
3. Under **Settings -> Keys**, copy the **PRIMARY CONNECTION STRING** (Do not copy the Primary Key; the connection string is much longer and starts with `AccountEndpoint=https://...`).

### Step 2: Create the Local Settings File
Create a new file at `api/local.settings.json` with this template:
```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "CosmosDBConnectionString": "<paste-your-actual-cosmos-connection-string-here>",
    "COSMOS_DATABASE": "HelpdeskDB",
    "COSMOS_CONTAINER": "Tickets"
  },
  "Host": {
    "CORS": "*"
  }
}
```
*(Save the file. The development server will automatically detect and load these settings at startup).*

### Step 3: Run and Verify
Restart your development server (`python scripts/dev_server.py`). Open [http://localhost:4280/api/health](http://localhost:4280/api/health) and verify that `"storage": "cosmos"` is shown.

---

## 5. Running Unit Tests

To run the unit test suite:
```bash
pytest tests -v
```

> [!NOTE]
> **Windows Timer Resolution Warning:** If running on Windows, you may see 3 test failures (`test_timestamps_carry_sub_second_precision`, `test_listing_is_newest_first`, and `test_timestamps_are_distinct_for_rapid_inserts`). This is a known Windows limitation where the system clock's sub-second resolution (~15ms) causes rapid back-to-back dictionary insertions to resolve to duplicate timestamps. On Linux/macOS or in production, these tests pass cleanly.

---

## 6. Step-by-Step Azure Deployment Guide

To deploy the backend securely in production without hardcoding keys, implement the following steps:

### Step A: Configure Key Vault Secret
1. Open your Azure Key Vault `kv-capstone-db` (ensure it is configured on the **Standard** tier).
2. Go to **Objects -> Secrets -> Generate/Import**.
3. Create a secret named `CosmosDBConnectionString` and paste the connection string you retrieved from Cosmos DB.

### Step B: Enable Managed Identity on the Function App
1. Go to your Function App `func-ai200-triage-service`.
2. Ensure the plan is **Consumption (Y1)** for free-tier compliance.
3. Under **Settings -> Identity**, toggle the Status to **On** under the **System assigned** tab, and save.

### Step C: Authorize the Function App in Key Vault
1. Go to your Key Vault `kv-capstone-db`.
2. Under **Settings -> Access policies**, click **Create**.
3. Grant **Get** and **List** permissions for **Secret permissions**.
4. Search for and select your Function App identity (`func-ai200-triage-service`) as the principal, and save.

### Step D: Link Key Vault to App Settings
1. Go back to your Function App `func-ai200-triage-service`.
2. Under **Settings -> Configuration -> Application settings**, add a new setting:
   * **Name**: `CosmosDBConnectionString`
   * **Value**: `@Microsoft.KeyVault(VaultName=kv-capstone-db;SecretName=CosmosDBConnectionString)`
3. Save the configurations. Azure will automatically resolve the secret at runtime.
