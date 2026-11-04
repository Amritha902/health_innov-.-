// Riaya on Microsoft Azure in a UAE region (UAE North = Dubai, UAE Central = Abu Dhabi).
// Creates: Linux App Service (Python 3.12) + Azure Database for PostgreSQL Flexible Server, both in the chosen UAE region.
// Deploy: see docs/AZURE.md.

@description('UAE region for every resource. uaenorth (Dubai) or uaecentral (Abu Dhabi).')
@allowed(['uaenorth', 'uaecentral'])
param location string = 'uaenorth'

@description('Short name used for every resource, lower case letters and digits.')
@minLength(3)
@maxLength(14)
param name string = 'riaya'

@description('Postgres administrator login.')
param dbAdmin string = 'riayaadmin'

@secure()
@description('Postgres administrator password (12+ characters, mixed).')
param dbPassword string

@secure()
@description('Fernet key for encryption at rest. Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"')
param dataKey string

@secure()
@description('Random salt for hashing WhatsApp numbers.')
param phoneSalt string

@description('First clinician username.')
param clinicianUser string

@secure()
@description('First clinician password: at least 12 varied characters, not containing the username.')
param clinicianPassword string

@description('True only once hosting, compliance and governance are confirmed for real patient data. Removes the demonstration banner.')
param uaeHosted bool = false

var suffix = uniqueString(resourceGroup().id)
var dbServerName = '${name}-db-${suffix}'

resource plan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: '${name}-plan'
  location: location
  kind: 'linux'
  sku: { name: 'B1', tier: 'Basic' }
  properties: { reserved: true }
}

resource db 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: dbServerName
  location: location
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '16'
    administratorLogin: dbAdmin
    administratorLoginPassword: dbPassword
    storage: { storageSizeGB: 32 }
    backup: { backupRetentionDays: 14, geoRedundantBackup: 'Disabled' }  // backups stay in the same region
    highAvailability: { mode: 'Disabled' }
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: db
  name: 'riaya'
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

// lets the App Service reach the database; tighten to VNet integration for a pilot
resource allowAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: db
  name: 'AllowAzureServices'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}

resource app 'Microsoft.Web/sites@2023-01-01' = {
  name: '${name}-${suffix}'
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      appCommandLine: 'python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000'
      healthCheckPath: '/api/health'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      alwaysOn: true
      appSettings: [
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'WEBSITES_PORT', value: '8000' }
        { name: 'DATABASE_URL', value: 'postgresql://${dbAdmin}:${uriComponent(dbPassword)}@${db.properties.fullyQualifiedDomainName}:5432/riaya?sslmode=require' }
        { name: 'RIAYA_DATA_KEY', value: dataKey }
        { name: 'RIAYA_PHONE_SALT', value: phoneSalt }
        { name: 'RIAYA_CLINICIAN_USER', value: clinicianUser }
        { name: 'RIAYA_CLINICIAN_PASSWORD', value: clinicianPassword }
        { name: 'RIAYA_UAE_HOSTED', value: uaeHosted ? 'true' : 'false' }
      ]
    }
  }
  dependsOn: [database, allowAzure]
}

output url string = 'https://${app.properties.defaultHostName}'
output appName string = app.name
