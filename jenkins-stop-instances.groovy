pipeline {
    agent any
    stages {
        stage('Stop Instances') {
            steps {
                script {
                    sh '''
                    chmod +x ~/git/ci-cd-pipelines/scripts/stop-instances.sh
                    ~/git/ci-cd-pipelines/scripts/stop-instances.sh
                    '''
                }
            }
        }
    }
}
