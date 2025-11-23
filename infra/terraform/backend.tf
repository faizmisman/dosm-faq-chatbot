terraform {
  backend "azurerm" {}
}

# Remote backend usage:
# Create or choose a storage account + container before first init.
# Example (one-time bootstrap):
#   az storage account create -n dosmtfstatesa -g dosm-faq-chatbot-data -l southeastasia --sku Standard_LRS --allow-blob-public-access false
#   az storage container create --name tfstate --account-name dosmtfstatesa
# Then run:
#   terraform init \
#     -backend-config="resource_group_name=dosm-faq-chatbot-data" \
#     -backend-config="storage_account_name=dosmtfstatesa" \
#     -backend-config="container_name=tfstate" \
#     -backend-config="key=infra.terraform.tfstate"
# For automation, keep backend config values in environment or a backend.hcl file.
