# Repository Reset Instructions

Follow ONLY if you intend to wipe remote history and replace with fresh scaffold.

```bash
# 1. Ensure you have a local working copy with new files
#    (You are here.)

# 2. Remove previous git data locally (optional if already clean)
rm -rf .git

git init
git add .
git commit -m "feat: reset repository with new Hailo RTSP pipeline scaffold"

git branch -M main

git remote add origin git@github.com:kyleengza/pi-live-detect-rstp.git

# 3. FORCE push (destructive)
git push -f origin main
```

After this push, old history is unrecoverable unless someone retained a clone.
