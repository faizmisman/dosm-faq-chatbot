terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.99"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.29"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "azurerm" {
  features {}
}

# Kubernetes providers for dev and prod clusters
## Reintroducing Kubernetes provider aliases now that AKS clusters exist
provider "kubernetes" {
  alias                  = "dev"
  host                   = azurerm_kubernetes_cluster.aks_dev.kube_config[0].host
  client_certificate     = base64decode(azurerm_kubernetes_cluster.aks_dev.kube_config[0].client_certificate)
  client_key             = base64decode(azurerm_kubernetes_cluster.aks_dev.kube_config[0].client_key)
  cluster_ca_certificate = base64decode(azurerm_kubernetes_cluster.aks_dev.kube_config[0].cluster_ca_certificate)
}

provider "kubernetes" {
  alias                  = "prod"
  host                   = azurerm_kubernetes_cluster.aks_prod.kube_config[0].host
  client_certificate     = base64decode(azurerm_kubernetes_cluster.aks_prod.kube_config[0].client_certificate)
  client_key             = base64decode(azurerm_kubernetes_cluster.aks_prod.kube_config[0].client_key)
  cluster_ca_certificate = base64decode(azurerm_kubernetes_cluster.aks_prod.kube_config[0].cluster_ca_certificate)
}
