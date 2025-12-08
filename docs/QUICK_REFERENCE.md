# GetMyEBook-Web - Quick Reference

## 🚀 First-Time Setup

```bash
# 1. Navigate to project directory
cd GetMyEBook-Web

# 2. Run the application
uv run cps.py

# 3. Follow the interactive setup wizard
# - Enter database host (default: localhost)
# - Enter database port (default: 5432)
# - Enter database username
# - Enter database password
# - Enter application database name
# - Enter Calibre database name

# 4. Application starts automatically after setup!
```

## 📋 Prerequisites Checklist

- [ ] Python 3.7+ installed
- [ ] PostgreSQL 12+ installed and running
- [ ] Database created for the application
- [ ] Database user with appropriate permissions
- [ ] UV package manager installed (or use pip)

## 🔧 Common Commands

### Run Application
```bash
uv run cps.py
```

### Reconfigure
```bash
# Delete .env to trigger setup wizard again
rm .env
uv run cps.py
```

### Manual Configuration
```bash
# Edit .env file directly
nano .env
```

### Clean Up Legacy Files
```bash
./scripts/cleanup_legacy_files.sh
```

## 📁 Important Files

| File | Purpose |
|------|---------|
| `.env` | Database credentials (auto-generated) |
| `SETUP_GUIDE.md` | Comprehensive setup documentation |
| `README.md` | Project overview and features |
| `cps/setup_manager.py` | Setup wizard code |
| `cps/utils.py` | Shared utilities |

## 🔐 Security Notes

- `.env` file has secure permissions (0600 on Unix)
- Never commit `.env` to version control (already gitignored)
- Use strong passwords for database credentials
- Regularly update dependencies

## 🐛 Troubleshooting Quick Fixes

### Setup wizard doesn't appear
```bash
rm .env
uv run cps.py
```

### Database connection failed
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection manually
psql -h localhost -p 5432 -U your_user -d your_database
```

### Missing dependencies
```bash
uv sync
# or
pip install -r requirements.txt
```

### Permission errors on .env
```bash
chmod 600 .env
```

## 📚 Documentation

- **Detailed Setup**: See [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **Implementation Details**: See [walkthrough.md](.gemini/antigravity/brain/*/walkthrough.md)
- **Environment Variables**: See [SETUP_GUIDE.md#environment-variables-reference](SETUP_GUIDE.md#environment-variables-reference)

## 🎯 What Was Implemented

✅ One-command automated setup  
✅ Interactive configuration wizard  
✅ Secure credential storage  
✅ Dynamic path resolution (works on any system)  
✅ Database connection validation  
✅ Automatic table creation  
✅ Comprehensive documentation  
✅ Legacy file cleanup utilities  

## 🔄 Migration from SQLite

If you have old SQLite databases:

1. **Backup first**:
   ```bash
   cp app.db app.db.backup
   cp metadata.db metadata.db.backup
   ```

2. **Run new setup** with PostgreSQL

3. **Archive old files**:
   ```bash
   ./scripts/cleanup_legacy_files.sh
   ```

## 💡 Tips

- Use default values when prompted (just press Enter)
- Test database connection before running setup
- Keep `.env` file secure and backed up
- Review SETUP_GUIDE.md for advanced configuration

## 🆘 Getting Help

1. Check [SETUP_GUIDE.md](SETUP_GUIDE.md) troubleshooting section
2. Review error messages carefully
3. Verify PostgreSQL is running and accessible
4. Check database credentials are correct

---

**Ready to start?** Just run: `uv run cps.py`
