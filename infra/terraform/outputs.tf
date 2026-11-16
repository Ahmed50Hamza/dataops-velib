output "dashboard_url_hint" {
  description = "Open the public IPv4 address of the running task on port 8000."
  value       = "Find the dataops-velib-api task in ECS, then open http://<public-ip>:8000"
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "s3_bucket_name" {
  value = aws_s3_bucket.data.bucket
}
