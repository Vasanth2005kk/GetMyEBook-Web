# GetMyEBook-Web Setup Guide

## Quick Start

GetMyEBook-Web now features an **automated setup wizard** that makes deployment incredibly simple. Just run:

```bash
uv run cps.py
```

On first run, the setup wizard will automatically launch and guide you through the configuration process.

## Prerequisites

Before running GetMyEBook-Web, ensure you have:

1. **Python 3.7 or higher**
   ```bash
   python3 --version
   ```

2. **PostgreSQL Database**
   - PostgreSQL server installed and running
   - Database created for the application
   - Database user with appropriate permissions

3. **UV Package Manager** (recommended)
   ```bash
   # Install uv if not already installed
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

4. **System Dependencies**
   - ImageMagick (for cover extraction)
   - libmagic (for file type detection)

## First-Run Setup

### Automated Setup (Recommended)

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd GetMyEBook-Web
   ```

2. **Run the application**:
   ```bash
   uv run cps.py
   ```

3. **Follow the setup wizard**:
   The wizard will prompt you for:
   - Database host (default: localhost)
   - Database port (default: 5432)
   - Database username
   - Database password
   - Application database name
   - Calibre database name

4. **Automatic configuration**:
   - The wizard validates your database connection
   - Creates a secure `.env` file with your credentials
   - Initializes all required database tables
   - Launches the application

### Manual Setup (Advanced Users)

If you prefer to configure manually:

1. **Create `.env` file** in the project root:
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env`** with your database credentials:
   ```env
   DB_USERNAME=your_db_user
   DB_PASSWORD=your_db_password
   DB_HOST=localhost
   DB_PORT=5432
   DATABASENAME_APP=calibreweb_app
   DATABASENAME_CALIBRE=calibreweb_calibre
   ```

3. **Set secure permissions** (Unix/Linux):
   ```bash
   chmod 600 .env
   ```

4. **Run the application**:
   ```bash
   uv run cps.py
   ```

## Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_USERNAME` | PostgreSQL username | `calibre_user` |
| `DB_PASSWORD` | PostgreSQL password | `secure_password_123` |
| `DB_HOST` | Database server hostname or IP | `localhost` or `192.168.1.100` |
| `DB_PORT` | Database server port | `5432` |
| `DATABASENAME_APP` | Main application database name | `calibreweb_app` |
| `DATABASENAME_CALIBRE` | Calibre library database name | `calibreweb_calibre` |

### Optional Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASENAME_DISCOURSE` | Discussion forum database name | `calibreweb_discourse` |
| `DATABASE_URL` | Complete database URL (overrides individual settings) | `postgresql+psycopg2://user:pass@host:port/db` |

## Database Setup

### Creating PostgreSQL Databases

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create user
CREATE USER calibre_user WITH PASSWORD 'your_secure_password';

# Create databases
CREATE DATABASE calibreweb_app OWNER calibre_user;
CREATE DATABASE calibreweb_calibre OWNER calibre_user;

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE calibreweb_app TO calibre_user;
GRANT ALL PRIVILEGES ON DATABASE calibreweb_calibre TO calibre_user;

# Exit
\q
```

### Verifying Database Connection

You can test your database connection manually:

```bash
psql -h localhost -p 5432 -U calibre_user -d calibreweb_app
```

## Troubleshooting

### Setup Wizard Not Appearing

**Problem**: The setup wizard doesn't launch even though `.env` doesn't exist.

**Solution**: 
- Ensure you're running from the project root directory
- Check that `cps/setup_manager.py` exists
- Try deleting `.env` if it exists but is incomplete

### Database Connection Failed

**Problem**: "Database connection failed" error during setup.

**Solutions**:
1. **Verify PostgreSQL is running**:
   ```bash
   sudo systemctl status postgresql
   ```

2. **Check database exists**:
   ```bash
   psql -U postgres -l | grep calibreweb
   ```

3. **Verify user permissions**:
   ```bash
   psql -U postgres -c "\du" | grep your_username
   ```

4. **Check PostgreSQL accepts connections**:
   - Edit `/etc/postgresql/*/main/pg_hba.conf`
   - Ensure there's a line like: `host all all 127.0.0.1/32 md5`
   - Restart PostgreSQL: `sudo systemctl restart postgresql`

### Missing Python Dependencies

**Problem**: `ImportError` or missing module errors.

**Solution**:
```bash
# Install dependencies
uv sync

# Or with pip
pip install -r requirements.txt
```

### Permission Denied on .env File

**Problem**: Cannot read or write `.env` file.

**Solution**:
```bash
# Fix ownership
sudo chown $USER:$USER .env

# Set proper permissions
chmod 600 .env
```

### Port Already in Use

**Problem**: Application fails to start because port 8083 is in use.

**Solution**:
1. **Find process using the port**:
   ```bash
   sudo lsof -i :8083
   ```

2. **Kill the process** or **change the port** in application settings.

### Database Tables Not Created

**Problem**: Application starts but database tables are missing.

**Solution**:
1. **Run setup wizard again**:
   ```bash
   # Delete .env to trigger setup
   rm .env
   uv run cps.py
   ```

2. **Or manually create tables** (advanced):
   ```python
   python3 -c "from cps.setup_manager import initialize_databases; initialize_databases(config)"
   ```

## Security Best Practices

### File Permissions

The `.env` file contains sensitive credentials. Ensure it's protected:

```bash
# Unix/Linux/macOS
chmod 600 .env

# Verify
ls -la .env
# Should show: -rw------- (owner read/write only)
```

### Database Security

1. **Use strong passwords**: Minimum 16 characters with mixed case, numbers, and symbols
2. **Limit database access**: Only allow connections from necessary hosts
3. **Regular backups**: Set up automated database backups
4. **Update regularly**: Keep PostgreSQL and all dependencies up to date

### Production Deployment

For production environments:

1. **Use environment-specific configurations**
2. **Enable SSL/TLS** for database connections
3. **Set up firewall rules** to restrict database access
4. **Use a reverse proxy** (nginx, Apache) in front of the application
5. **Enable HTTPS** with valid SSL certificates
6. **Regular security audits** and dependency updates

## Reconfiguration

To reconfigure the application after initial setup:

### Option 1: Delete and Re-run Setup

```bash
# Backup current .env (optional)
cp .env .env.backup

# Delete .env
rm .env

# Run application (setup wizard will launch)
uv run cps.py
```

### Option 2: Manual Edit

```bash
# Edit .env file
nano .env  # or vim, code, etc.

# Restart application
uv run cps.py
```

## Migration from SQLite

If you're migrating from an older SQLite-based installation:

1. **Backup your SQLite databases**:
   ```bash
   cp app.db app.db.backup
   cp metadata.db metadata.db.backup
   ```

2. **Export data** (if needed for migration)

3. **Run the new setup** with PostgreSQL credentials

4. **Archive old SQLite files**:
   ```bash
   mkdir legacy
   mv *.db legacy/
   ```

## Additional Resources

- **Main README**: [README.md](README.md)
- **Discussion Forum Setup**: [DISCUSSION_README.md](DISCUSSION_README.md)
- **Contributing Guide**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Security Policy**: [SECURITY.md](SECURITY.md)

## Getting Help

If you encounter issues not covered in this guide:

1. Check the [GitHub Issues](https://github.com/your-repo/issues)
2. Join the [Discord Community](https://discord.gg/your-invite)
3. Review the [Wiki](https://github.com/your-repo/wiki)

## Advanced Configuration

### Custom Database URL

Instead of individual variables, you can use a complete DATABASE_URL:

```env
DATABASE_URL=postgresql+psycopg2://user:password@host:port/database
```

This will override individual DB_* variables.

### Multiple Environments

For development/staging/production setups:

```bash
# Development
cp .env .env.development

# Production
cp .env .env.production

# Use specific env file
export ENV_FILE=.env.production
uv run cps.py
```

### Docker Deployment

For Docker deployments, pass environment variables directly:

```bash
docker run -e DB_USERNAME=user -e DB_PASSWORD=pass ... your-image
```

Or use a `.env` file with docker-compose:

```yaml
services:
  calibreweb:
    env_file:
      - .env
```
