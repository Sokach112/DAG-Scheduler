git add -A
git commit -m "feat: CORS env var + project outline"
git checkout main
git pull origin main
git merge --no-ff feature/api -m "API initially done, merged."
git push origin main
git branch -d feature/api