pipeline {
    agent any
    environment {
        IMAGE_NAME = 'campusiq-student-portal'
    }
    stages {
        stage('Checkout') {
            steps { checkout scm }
        }
        stage('Build Docker image') {
            steps { sh 'docker build -t ${IMAGE_NAME}:${BUILD_NUMBER} .' }
        }
        stage('API smoke test') {
            steps {
                sh '''
                  docker run -d --name campusiq-smoke -p 18000:8000 ${IMAGE_NAME}:${BUILD_NUMBER}
                  sleep 8
                  curl --fail http://localhost:18000/api/health
                '''
            }
            post { always { sh 'docker rm -f campusiq-smoke || true' } }
        }
    }
    post {
        success { echo 'CampusIQ image built and API smoke test passed.' }
        failure { echo 'Build or smoke test failed. Review console output.' }
    }
}
