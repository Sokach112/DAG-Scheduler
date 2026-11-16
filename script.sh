git add -A
git commit -m "feat: add JSON serialization for Plan"
git checkout main
git pull origin main
git merge --no-ff feature/serializer
git push origin main
git branch -d feature/serializer