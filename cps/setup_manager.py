#!/usr/bin/env python
# -*- coding: utf-8 -*-

#  This file is part of the Calibre-Web (https://github.com/janeczku/calibre-web)
#    Copyright (C) 2025 GetMyEBook-Web Contributors
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program. If not, see <http://www.gnu.org/licenses/>.

"""
Setup Manager for GetMyEBook-Web

Handles first-run setup, configuration, and database initialization.
"""

import os
import sys
import getpass
from .utils import (
    get_project_root,
    get_env_path,
    set_secure_permissions,
    check_file_permissions,
    validate_port,
    validate_hostname
)
import secrets

def generate_secret_key(length=32):
    """Generates a random text string in hexadecimal format."""
    return secrets.token_hex(length)

def is_first_run():
    """
    Check if this is the first run (no .env file or incomplete configuration).
    
    Returns:
        bool: True if setup is needed, False otherwise
    """
    env_path = get_env_path()
    
    # If .env doesn't exist, it's definitely first run
    if not os.path.exists(env_path):
        return True
    
    # Check if .env has all required variables (only 4 needed)
    required_vars = [
        'DB_USERNAME',
        'DB_PASSWORD',
        'DB_HOST',
        'DB_PORT'
    ]
    
    try:
        from dotenv import dotenv_values
        env_vars = dotenv_values(env_path)
        
        # Check if all required variables are present and non-empty
        for var in required_vars:
            if var not in env_vars or not env_vars[var]:
                return True
        
        return False
    except Exception:
        # If we can't read the file, assume first run
        return True


def print_banner():
    """Print welcome banner for setup wizard."""
    print("\n" + "="*60)
    print("  GetMyEBook-Web - First Run Setup Wizard")
    print("="*60)
    print("\nWelcome! This wizard will help you configure your application.")
    print("You'll need PostgreSQL database credentials to continue.\n")


def get_user_input(prompt, default=None, password=False, validator=None):
    """
    Get user input with optional default value and validation.
    
    Args:
        prompt (str): Prompt to display
        default (str, optional): Default value
        password (bool): If True, hide input (for passwords)
        validator (callable, optional): Function to validate input
        
    Returns:
        str: User input or default value
    """
    while True:
        if default:
            display_prompt = f"{prompt} [{default}]: "
        else:
            display_prompt = f"{prompt}: "
        
        if password:
            value = getpass.getpass(display_prompt)
        else:
            value = input(display_prompt)
        
        # Use default if no input provided
        if not value and default:
            value = default
        
        # Validate if validator provided
        if validator:
            is_valid, error = validator(value)
            if not is_valid:
                print(f"Error: {error}")
                continue
        
        return value


def validate_database_connection(host, port, username, password, database):
    """
    Test database connection with provided credentials. If database does not exist, create it.
    Args:
        host (str): Database host
        port (int): Database port
        username (str): Database username
        password (str): Database password
        database (str): Database name
    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    try:
        import urllib.parse
        from sqlalchemy import create_engine, text
        import psycopg2
        # Encode password for URL
        encoded_password = urllib.parse.quote_plus(password)
        database_url = f"postgresql+psycopg2://{username}:{encoded_password}@{host}:{port}/{database}"
        print(f"Testing connection to: {database_url}")
        # Try to connect 
        engine = create_engine(database_url, pool_pre_ping=True)
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            engine.dispose()
            return True, None
        except Exception as e:
            # Check if error is database does not exist
            if "does not exist" in str(e):
                print(f"Database '{database}' does not exist. Attempting to create...")
                # Connect to default 'postgres' database with AUTOCOMMIT
                default_url = f"postgresql+psycopg2://{username}:{encoded_password}@{host}:{port}/postgres"
                default_engine = create_engine(default_url, pool_pre_ping=True, isolation_level="AUTOCOMMIT")
                try:
                    with default_engine.connect() as conn:
                        conn.execute(text(f"CREATE DATABASE {database}"))
                    default_engine.dispose()
                    print(f"Database '{database}' created successfully.")
                    # Try connecting again
                    engine = create_engine(database_url, pool_pre_ping=True)
                    with engine.connect() as conn:
                        result = conn.execute(text("SELECT 1"))
                        result.fetchone()
                    engine.dispose()
                    return True, None
                except Exception as ce:
                    return False, f"Failed to create database '{database}': {ce}"
            else:
                return False, f"Database connection failed: {e}"
    except ImportError as e:
        return False, f"Missing required package: {e}. Please install psycopg2-binary and sqlalchemy."
    except Exception as e:
        return False, f"Database connection failed: {e}"


def create_env_file(config):
    """
    Create .env file with provided configuration.
    
    Args:
        config (dict): Configuration dictionary
        
    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    env_path = get_env_path()
    
    try:
        # Create .env content
        env_content = f"""# -------------------------
# Database Login Details
# -------------------------
# Generated by GetMyEBook-Web Setup Wizard
# Date: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# secret key
SECRET_KEY={generate_secret_key()}

DB_USERNAME={config['db_username']}
DB_PASSWORD={config['db_password']}
DB_HOST={config['db_host']}
DB_PORT={config['db_port']}

# -------------------------
# Database Names
# -------------------------
DATABASENAME_APP={config['db_name_app']}
# -------------------------
# Optional: Full Database URL
# -------------------------
# Uncomment and modify if you prefer to use a single DATABASE_URL
DATABASE_URL=postgresql+psycopg2://{config['db_username']}:{config['db_password']}@{config['db_host']}:{config['db_port']}/{config['db_name_app']}
# books and book page covers loaction path 
BOOK_FILEPATH={config['book_location_path']}
"""
        
        # Write to file
        with open(env_path, 'w') as f:
            f.write(env_content)
        
        # Set secure permissions
        set_secure_permissions(env_path)
        
        # Verify permissions
        is_secure, warning = check_file_permissions(env_path)
        if not is_secure:
            print(f"\nWarning: {warning}")
        
        return True, None
        
    except Exception as e:
        return False, f"Failed to create .env file: {e}"


def initialize_databases(config):
    """
    Initialize database tables.
    
    Args:
        config (dict): Configuration dictionary
        
    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    try:
        import urllib.parse
        from sqlalchemy import create_engine
        from sqlalchemy.orm import scoped_session, sessionmaker
        
        # Encode password for URL
        encoded_password = urllib.parse.quote_plus(config['db_password'])
        database_url = f"postgresql+psycopg2://{config['db_username']}:{encoded_password}@{config['db_host']}:{config['db_port']}/{config['db_name_app']}"
        
        # Create engine
        engine = create_engine(database_url, pool_pre_ping=True)
        
        # Import models
        from . import ub
        from . import config_sql
        
        # Create tables
        print("Creating application database tables...")
        ub.Base.metadata.create_all(engine)
        config_sql._Base.metadata.create_all(engine)
        
        engine.dispose()
        return True, None
        
    except Exception as e:
        return False, f"Failed to initialize databases: {e}"


def run_interactive_setup():
    """
    Run the interactive setup wizard.
    
    Returns:
        bool: True if setup completed successfully, False otherwise
    """
    print_banner()
    
    # Collect database configuration (only 4 inputs)
    print("Database Configuration")
    print("-" * 60)
    print("Note: Database names are automatically set to 'getmyebook_app' and 'getmyebook_calibre'")
    print()
    
    db_host = get_user_input(
        "Database Host",
        default="localhost",
        validator=validate_hostname
    )
    
    db_port = get_user_input(
        "Database Port",
        default="5432",
        validator=lambda p: (validate_port(p)[0], validate_port(p)[2])
    )
    
    db_username = get_user_input(
        "Database Username",
        default=''
    )
    
    db_password = get_user_input(
        "Database Password",
        default=''
    )
    
    db_name_app = get_user_input(
        "Database Name",
        default=""
    )

    book_location_path =  get_user_input(
        "Books and Books Cover Path "
    )
    
    # Test database connection
    print("\n" + "-" * 60)
    print("Testing database connection...")
    
    success, error = validate_database_connection(
        db_host,
        int(db_port),
        db_username,
        db_password,
        db_name_app
    )
    
    if not success:
        print(f"\n❌ {error}")
        print("\nSetup failed. Please check your database configuration and try again.")
        return False
    
    print("✓ Database connection successful!")
    
    # Create configuration dictionary
    config = {
        'db_host': db_host,
        'db_port': db_port,
        'db_username': db_username,
        'db_password': db_password,
        'db_name_app': db_name_app,
        'book_location_path': book_location_path
    }
    
    # Create .env file
    print("\nCreating configuration file...")
    success, error = create_env_file(config)
    
    if not success:
        print(f"\n❌ {error}")
        return False
    
    print(f"✓ Configuration saved to: {get_env_path()}")
    
    # Initialize databases
    print("\nInitializing databases...")
    success, error = initialize_databases(config)
    
    if not success:
        print(f"\n❌ {error}")
        print("\nWarning: Database tables may not have been created.")
        print("You can try running the application anyway, or check the error above.")
        
        response = input("\nContinue anyway? (yes/no): ")
        if response.lower() != 'yes':
            return False
    else:
        print("✓ Database tables created successfully!")
    
    # Setup complete
    print("\n" + "="*60)
    print("  Setup Complete!")
    print("="*60)
    print("\nYour application is now configured and ready to use.")
    print("Starting GetMyEBook-Web...\n")
    
    return True


def reconfigure():
    """
    Allow user to reconfigure the application.
    
    Returns:
        bool: True if reconfiguration completed successfully
    """
    env_path = get_env_path()
    
    if os.path.exists(env_path):
        print(f"\nExisting configuration found at: {env_path}")
        response = input("This will overwrite your existing configuration. Continue? (yes/no): ")
        
        if response.lower() != 'yes':
            print("Reconfiguration cancelled.")
            return False
    
    return run_interactive_setup()
