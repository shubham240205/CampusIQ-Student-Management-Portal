
pipeline {
    agent any

    environment {
        IMAGE_NAME = 'campusiq-student-portal'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker image') {
            steps {
                sh 'docker build -t ${IMAGE_NAME}:${BUILD_NUMBER} .'
            }
        }

        stage('API smoke test') {
            steps {
                sh '''
                    docker run -d --name campusiq-smoke \
                        -p 18000:8000 \
                        ${IMAGE_NAME}:${BUILD_NUMBER}

                    for i in $(seq 1 30); do
                        if curl --fail http://host.docker.internal:18000/api/health; then
                            echo "API smoke test passed!"
                            exit 0
                        fi

                        echo "Waiting for application... attempt $i"
                        sleep 2
                    done

                    echo "API smoke test failed!"
                    exit 1
                '''
            }

            post {
                always {
                    sh 'docker rm -f campusiq-smoke || true'
                }
            }
        }
    }

    post {
        success {
            echo 'CampusIQ image built and API smoke test passed.'
        }

        failure {
            echo 'Build or smoke test failed. Review console output.'
        }
    }
}
