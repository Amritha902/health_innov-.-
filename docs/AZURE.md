# Deploying Riaya on Microsoft Azure in the UAE

Riaya runs on Azure App Service, with Azure Database for PostgreSQL holding the data. Both are placed in a UAE region:

- **UAE North:** Dubai.
- **UAE Central:** Abu Dhabi.

So the app, the database and its backups stay in the country. This uses the Azure credits that the challenge provides. The template is `azure/main.bicep`.

## What gets created

| Resource | Size | Purpose |
|---|---|---|
| App Service plan (Linux) | B1 | Runs the FastAPI app and serves the web app |
| Web App (Python 3.12) | — | HTTPS only, TLS 1.2+, health check at `/api/health`, FTP off |
| PostgreSQL Flexible Server 16 | Burstable B1ms, 32 GB | All records. Answers and messages are also encrypted by the app. Backups are kept 14 days in the same region |

## Deploy (about 10 minutes)

You need the Azure CLI (`az`) and an account with the challenge credits.

1. Sign in and create a resource group in the UAE:

   ```bash
   az login
   ```

   ```bash
   az group create --name riaya-rg --location uaenorth
   ```

2. Generate the secrets. Keep them in a password manager, not in the repository:

   ```bash
   python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   Run that once for the data key. Then run the next command twice: once for the phone salt, and once for the database password.

   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(24))"
   ```

3. Create the resources:

   ```bash
   az deployment group create --resource-group riaya-rg --template-file azure/main.bicep --parameters dbPassword='<db password>' dataKey='<data key>' phoneSalt='<salt>' clinicianUser='<username>' clinicianPassword='<strong password>'
   ```

   The output gives the app name and its `https://` address.

4. Upload the code. Run this from the repository root; App Service installs `requirements.txt` itself:

   ```bash
   zip -r riaya.zip backend web knowledge data requirements.txt -x "data/app.db" "data/secret.key"
   ```

   ```bash
   az webapp deploy --resource-group riaya-rg --name <appName from step 3> --src-path riaya.zip --type zip
   ```

5. Open the address and check that `/api/health` returns `{"ok": true}`. Then sign in to `/clinician.html` with the clinician account from step 3.

## Before real patient data

The deployment keeps `uaeHosted=false`, so every page still shows the demonstration banner. Change it to `true` only once all of these are done:

- **Hosting approval:** the DoH Abu Dhabi health-information standard (ADHICS) review of the hosting is complete.
- **Private network:** the database is moved onto a private network (VNet integration and a private endpoint), replacing the `AllowAzureServices` firewall rule.
- **Key Vault:** the secrets are moved into Azure Key Vault and referenced from the app settings.
- **Governance:** clinical governance and a security review are signed off.

Backup, restore and retention steps are in [OPERATIONS.md](OPERATIONS.md).
