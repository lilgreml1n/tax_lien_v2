# Migration Guide: Local (Mac) -> DGX (Linux)

This guide walks you through moving the Tax Lien v2 system from your local Mac to the DGX server.

## ✅ What Will Be Migrated
- **Database:** Full MySQL backup (even while running).
- **Backend:** Python code, Docker configuration.
- **Frontend:** React code + new Docker configuration (to run it easily).
- **Data Files:** PDFs/Excel files you added.

## 🚫 What Will NOT Be Migrated
- **Passwords/.env:** Excluded for security. You will recreate the `.env` on the DGX.
- **Node Modules/Virtual Envs:** Re-downloaded/built fresh on the DGX to ensure Linux compatibility.

---

## Step 1: Prepare on Local Mac

We have created a helper script to do the heavy lifting.

1. **Run the preparation script:**
   ```bash
   ./scripts/prepare_migration.sh
   ```

   This will:
   - Dump your running database to `lienhunter_backup.sql`.
   - Create a `tax_lien_v2_migration.tar.gz` archive of your code.
   - Generate a `restore_on_dgx.sh` script for the other side.

---

## Step 2: Transfer to DGX

Copy the files to your DGX server using `scp`. 
*Replace `user` with your actual DGX username (e.g., `ubuntu`, `root`, or your name).*

```bash
scp tax_lien_v2_migration.tar.gz lienhunter_backup.sql restore_on_dgx.sh user@192.168.100.133:~/
```

---

## Step 3: Restore on DGX

1. **SSH into the DGX:**
   ```bash
   ssh user@192.168.100.133
   ```

2. **Create a directory and move files:**
   ```bash
   mkdir -p ~/tax_lien_v2
   mv tax_lien_v2_migration.tar.gz lienhunter_backup.sql restore_on_dgx.sh ~/tax_lien_v2/
   cd ~/tax_lien_v2
   ```

3. **Unpack the archive:**
   ```bash
   tar -xzf tax_lien_v2_migration.tar.gz
   ```

4. **Run the restore script:**
   ```bash
   chmod +x restore_on_dgx.sh
   ./restore_on_dgx.sh
   ```

5. **Configure Secrets:**
   The script will pause and ask you to edit `.env`.
   - It will create a `.env` file from `.env.sample`.
   - Open it with `nano .env` or `vim .env`.
   - **Crucial:** Update `DATABASE_URL` (usually default is fine for Docker), but verify your passwords.
   - **Crucial:** Update `VITE_API_URL` to `http://192.168.100.133:8001` if you want to access it from your laptop.

---

## Step 4: Verification

Once the script finishes:

1. **Check Backend:**
   ```bash
   curl http://localhost:8001/docs
   ```

2. **Check Frontend:**
   Open your browser on your laptop and go to:
   `http://192.168.100.133:8082`

---

## Step 5: Clean Up Local (Optional)

Once you verify the DGX is running perfectly, you can stop the local containers to save resources on your Mac:

```bash
docker-compose down
```
