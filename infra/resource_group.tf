# Everything this stack creates carries the tag Project=homedocs (see default_tags
# in versions.tf). This group lists all of it in the console under
# Resource Groups & Tag Editor, so it's easy to see what the project runs.
resource "aws_resourcegroups_group" "homedocs" {
  # The description allows only letters, digits, spaces, _ . and - (no "+").
  name        = var.name
  description = "All resources for the HomeDocs Alexa Plus hackathon project"

  resource_query {
    query = jsonencode({
      ResourceTypeFilters = ["AWS::AllSupported"]
      TagFilters = [{
        Key    = "Project"
        Values = ["homedocs"]
      }]
    })
  }
}
