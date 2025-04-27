pipeline {
    agent any
    stages {
        stage('Start Instances') {
            steps {
                script {
                    sh '''
                    chmod +x ~/git/ci-cd-pipelines/scripts/start-instances.sh
                    ~/git/ci-cd-pipelines/scripts/start-instances.sh
                    '''
                }
            }
        }
    }
}
