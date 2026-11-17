git commit -a -m "feat: FastAPI layer updated."
git checkout main
git pull origin main
git merge --no-ff feature/api
git push origin main
git branch -d feature/api
