
# (I) Setup Google Cloud SDK CLI (if not done already)

1. Install Google CLoud SDK Shell

## (II) Set up Google Cloud SDK Shell

1. To initialize the gcloud CLI, run the following command: ```gcloud init```
2. In the browser window that opens, select the signed in google account which administers the Google App Engine project, in this case "smartcity907@gmail.com".
3. Check if authentication successful by running: ```gcloud projects list```. This should show the project "satellite-crop-monitoring"
4. Select the project by running the command: ```gcloud config set project satellite-crop-monitoring```

## Testing the application locally with cloud services like cloud database and storage

1. In the same greenareacloud repository/folder for the online application, switch branch to loc from main using the branch icon on the bottom of VS Code or doing `git switch loc`
2. Run the main.py program.
3. Open the application by putting in the address [https://localhost:5000](https://localhost:5000) into the browser. 
**Make sure to visit the application using this address or the authentication won't work properly**

## Testing the application locally with local database and storage

1. Open the greenarea-loc folder/repository.
2. Run the main.py program.
3. Open the application by putting in the address [https://localhost:5000](https://localhost:5000) into the browser. 
**Make sure to visit the application using this address or the authentication won't work properly**

## Updating the application deployed on the cloud
6. Now open the the directory of the project in the shell by running `cd <the path of the directory>`
7. To update the online deployed application:
    1. First make sure, you are in the main branch of the github repository by:
        - looking at the ribbon at the bottom of Visual Studio Code with the branch icon showing main.
    OR
        - running `git branch` which would list all branches and should highlight the "main" branch with the star and in green font colour.

        If branch is not main, select the main branch by clicking on the bottom branch icon in VS COde or running `git switch main`
    2. run: `gcloud app deploy` to deploy the updated   project to the main application.

        OR

        If you want to test out the updated project run `gcloud app deploy --promote`. This will deploy the updated project to a special URL given out by the shell after you run the command. The main application will remain unchanged.
