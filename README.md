# CampusIQ — OULAD-powered Student Management Portal

A full-stack academic analytics portal built with FastAPI, PostgreSQL, Docker and a role-based UI. It uses the genuine Open University Learning Analytics Dataset (OULAD), not fabricated academic marks.

## Dataset setup

Download the official OULAD archive from:
https://archive.ics.uci.edu/dataset/349/open+university+learning+analytics+dataset

Extract these files into `data/oulad/`:
- `studentInfo.csv`
- `studentAssessment.csv`
- `assessments.csv`
- `courses.csv`
- `studentRegistration.csv`
- `studentVle.csv`
- `vle.csv`
- `OULAD.names` (documentation)

The importer checks that all seven CSVs exist. It streams the 10.6M-row `studentVle.csv` file and stores aggregated engagement by student and course presentation; it does not load the entire file into RAM.

## Start the database and app

1. Copy `.env.example` to `.env`.
2. Change `POSTGRES_PASSWORD` and `SECRET_KEY`.
3. Start services:

```powershell
docker compose up --build -d db portal
```

4. Import OULAD once:

```powershell
docker compose run --rm importer
```

5. Open http://localhost:8000

Check API health at http://localhost:8000/api/health and interactive API docs at http://localhost:8000/docs.

## Demo staff accounts

| Role | Email | Password |
|---|---|---|
| Teacher | teacher@campus.edu | Teacher@123 |
| Admin | admin@campus.edu | Admin@123 |

One student login is created per unique OULAD `id_student` (the source has 32,593 student-course rows and 28,785 unique student IDs). Email format is `student<id_student>@oulad.local`; password for the local demo is `Student@123`. For example, use a real ID from `studentInfo.csv` to sign in. Do not expose these shared demo credentials in a public deployment.

## Data interpretation and limitations

- OULAD assessment scores are real dataset scores and are shown as assessment results.
- VLE clicks and active days are learning-platform engagement indicators, **not physical attendance**.
- Physical attendance is a separate teacher-entered feature and is blank until a teacher records it.
- OULAD final result categories are retained in the registration record for future reporting.
- OULAD is an anonymised historical dataset, not a live university feed. Student display names are generated labels based on anonymised IDs, not real identities.
- Risk labels in this educational demo are transparent rules, not a validated predictive model or a diagnosis. They should not be used for consequential decisions without institutional validation.

## Dataset scale

The official archive includes student information, registration, assessments, course presentations and VLE activity. The VLE CSV contains more than 10 million interaction rows. Import progress is printed in the terminal.

## Architecture

- FastAPI backend and REST API
- PostgreSQL database
- SQLAlchemy ORM
- Docker Compose
- OULAD streaming importer
- Jenkins pipeline for Docker build and API smoke test
- GitHub Actions Docker build workflow

## AWS / DevOps extension

Recommended deployment path:
1. Provision Ubuntu EC2 in your selected AWS region.
2. Install Docker Engine and Compose.
3. Use Terraform to provision EC2, security groups and IAM resources.
4. Use Ansible to configure the host and deploy the Compose project.
5. Put Nginx in front of the app and configure HTTPS.
6. Configure CloudWatch Agent for system and application logs.
7. For production, use RDS PostgreSQL in private subnets, store secrets securely, enable backups and restrict database network access.
8. Run Jenkins on a separate controlled host or use an existing Jenkins server. Keep Jenkins off the public internet where possible; configure credentials securely.

AWS links:
- https://console.aws.amazon.com/ec2/
- https://console.aws.amazon.com/rds/
- https://console.aws.amazon.com/cloudwatch/
- https://console.aws.amazon.com/iam/
- https://docs.aws.amazon.com/
- https://www.jenkins.io/doc/
- https://docs.docker.com/

AWS resources may incur charges. Check account/Academy restrictions and stop or delete lab resources when finished.

## Important

This is a student project baseline, not production-ready student information software. Before using real student data, implement individual account provisioning, unique passwords, password reset, audit logs, HTTPS, secret management, backups, rate limiting, privacy controls and institutional authorization. Change all demo credentials and secrets before any internet-facing deployment.
