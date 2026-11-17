git commit -a --allow-empty-message -m ""
git checkout main
git pull origin main
git merge --no-ff feature/what-if -m "what-if implemented."
git push origin main
git branch -d feature/what-if