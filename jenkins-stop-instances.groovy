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
        stage('Stop Instances') {
            steps {
                script {
                    sh '''
                    chmod +x scripts/stop-instances.sh
                    ./scripts/stop-instances.sh
                    '''
                }
            }
        }
    }
}
