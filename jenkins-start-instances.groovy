
pipeline {
    agent any
    stages {
        stage('Checkout') {
            steps {
                git branch: 'main',
                    credentialsId: 'github-app',
                    url: 'https://github.com/raafa001/spot-render.git'
            }
        }
        stage('Start Instances') {
            steps {
                script {
                    sh '''
                    chmod +x scripts/start-instances.sh
                    ./scripts/start-instances.sh
                    '''
                }
            }
        }
    }
}
