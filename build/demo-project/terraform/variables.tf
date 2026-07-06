variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "api_replicas" {
  type    = number
  default = 3
}

variable "release_tag" {
  type = string
}
