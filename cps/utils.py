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
Shared utility functions for GetMyEBook-Web
"""

import os
import sys
import stat

from . import logger

log = logger.create()


def get_project_root():
    """
    Get the project root directory dynamically.
    
    This function works regardless of where the script is called from,
    by finding the directory containing the cps package.
    
    Returns:
        str: Absolute path to the project root directory
    """
    # Get the directory containing this file (cps/)
    cps_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one level to get project root
    project_root = os.path.dirname(cps_dir)
    return project_root


def get_env_path():
    """
    Get the path to the .env file.
    
    Returns:
        str: Absolute path to the .env file
    """
    return os.path.join(get_project_root(), '.env')

def get_metadata_path(path=None):
    """
    Get the path to the metadata file.
    Returns:
        str: Absolute path to the metadata file
    """
    if path:
        log.info(f"Using custom metadata path: {path}")
        return path
    return os.path.join(get_project_root(), 'library/metadata.db') 


def ensure_directory_exists(directory_path):
    """
    Create a directory if it doesn't exist.
    
    Args:
        directory_path (str): Path to the directory
        
    Returns:
        bool: True if directory exists or was created, False on error
    """
    try:
        if not os.path.exists(directory_path):
            os.makedirs(directory_path, mode=0o755)
        return True
    except Exception as e:
        log.error(f"Error creating directory {directory_path}: {e}")
        return False


def set_secure_permissions(file_path):
    """
    Set secure file permissions for sensitive files.
    
    On Unix-like systems: Sets permissions to 0600 (read/write for owner only)
    On Windows: Attempts to set restricted ACL
    
    Args:
        file_path (str): Path to the file
        
    Returns:
        bool: True if permissions were set successfully, False otherwise
    """
    try:
        if os.name == 'posix':  # Unix-like systems (Linux, macOS)
            os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
            return True
        elif os.name == 'nt':  # Windows
            try:
                import win32security
                import ntsecuritycon as con
                
                # Get the current user
                user, domain, type = win32security.LookupAccountName("", os.getlogin())
                
                # Create a new DACL
                sd = win32security.GetFileSecurity(file_path, win32security.DACL_SECURITY_INFORMATION)
                dacl = win32security.ACL()
                
                # Add ACE for current user with full control
                dacl.AddAccessAllowedAce(win32security.ACL_REVISION, con.FILE_ALL_ACCESS, user)
                
                # Set the DACL
                sd.SetSecurityDescriptorDacl(1, dacl, 0)
                win32security.SetFileSecurity(file_path, win32security.DACL_SECURITY_INFORMATION, sd)
                return True
            except ImportError:
                # pywin32 not available, skip Windows ACL setting
                log.warning(f"Warning: pywin32 not available. Cannot set Windows file permissions.")
                log.info(f"Please ensure .env file is protected manually.")
                return False
        return True
    except Exception as e:
        log.warning(f"Warning: Could not set secure permissions on {file_path}: {e}")
        return False


def check_file_permissions(file_path):
    """
    Check if a file has secure permissions.
    
    Args:
        file_path (str): Path to the file
        
    Returns:
        tuple: (is_secure: bool, warning_message: str or None)
    """
    if not os.path.exists(file_path):
        return False, "File does not exist"
    
    if os.name == 'posix':
        # Check Unix permissions
        file_stat = os.stat(file_path)
        mode = file_stat.st_mode
        
        # Check if file is readable by group or others
        if mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH):
            return False, f"File {file_path} has insecure permissions. Run: chmod 600 {file_path}"
        
        return True, None
    
    # For Windows, we'll assume it's secure if we can't check
    return True, None


def validate_port(port_str):
    """
    Validate that a port number is valid.
    
    Args:
        port_str (str): Port number as string
        
    Returns:
        tuple: (is_valid: bool, port: int or None, error_message: str or None)
    """
    try:
        port = int(port_str)
        if 1 <= port <= 65535:
            return True, port, None
        else:
            return False, None, "Port must be between 1 and 65535"
    except ValueError:
        return False, None, "Port must be a number"


def validate_hostname(hostname):
    """
    Basic validation for hostname or IP address.
    
    Args:
        hostname (str): Hostname or IP address
        
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if not hostname or not hostname.strip():
        return False, "Hostname cannot be empty"
    
    # Basic validation - just check it's not empty and doesn't contain invalid characters
    invalid_chars = [' ', '\n', '\r', '\t']
    for char in invalid_chars:
        if char in hostname:
            return False, f"Hostname contains invalid character: {repr(char)}"
    
    return True, None


def is_running_in_venv():
    """
    Check if the script is running in a virtual environment.
    
    Returns:
        bool: True if running in a virtual environment
    """
    return (hasattr(sys, 'real_prefix') or
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))
