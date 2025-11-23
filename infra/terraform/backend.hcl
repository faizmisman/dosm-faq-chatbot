# AzureRM backend configuration (non-sensitive values ok to commit)
# If storage account/container do not yet exist, create them first:
#   az storage account create -n dosmtfstatesa -g dosm-faq-chatbot-data -l southeastasia --sku Standard_LRS --allow-blob-public-access false
#   az storage container create --name tfstate --account-name dosmtfstatesa
#
# Then run:
#   terraform init -backend-config=backend.hcl
#
# For automation with service principal, export ARM_* env vars before init.
# Optional flags: use_azuread_auth=true (if using OIDC or SP AAD auth). Remove if unsupported.

resource_group_name  = "dosm-faq-chatbot-data"
storage_account_name = "dosmfaqtfstate01"
container_name       = "tfstate"
key                  = "infra.terraform.tfstate"
# use_azuread_auth   = true  # uncomment if using ARM_CLIENT_ID/SECRET or federated credentials
