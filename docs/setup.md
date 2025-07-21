# ⚙️ Setup Guide

## 🎯 Prerequisites

Before setting up the Developer Dashboard, ensure you have the following installed:

### System Requirements
- **Python 3.8+** (recommended: Python 3.9 or higher)
- **Git** for version control
- **pip** for Python package management
- **Virtual environment** support (venv, virtualenv, or conda)

### External Dependencies
- **GitHub Personal Access Token** with repository permissions
- **Internet connection** for GitHub API access
- **Modern web browser** (Chrome, Firefox, Safari, Edge)

---

## 🚀 Installation Steps

### 1. Clone the Repository

```bash
# Clone the repository
git clone https://github.com/your-username/developer-dashboard.git

# Navigate to the project directory
cd developer-dashboard

# Verify the project structure
ls -la
```

Expected output:
```
total 128
drwxr-xr-x   8 user  staff   256 Jul 16 10:00 .
drwxr-xr-x  10 user  staff   320 Jul 16 10:00 ..
drwxr-xr-x  12 user  staff   384 Jul 16 10:00 .git
-rw-r--r--   1 user  staff   142 Jul 16 10:00 .gitignore
-rw-r--r--   1 user  staff 14336 Jul 16 10:00 README.md
-rw-r--r--   1 user  staff 18432 Jul 16 10:00 app.py
drwxr-xr-x   3 user  staff    96 Jul 16 10:00 data
drwxr-xr-x   4 user  staff   128 Jul 16 10:00 docs
-rw-r--r--   1 user  staff 71680 Jul 16 10:00 github_service.py
-rw-r--r--   1 user  staff    53 Jul 16 10:00 requirements.txt
drwxr-xr-x   3 user  staff    96 Jul 16 10:00 static
drwxr-xr-x   6 user  staff   192 Jul 16 10:00 templates
```

### 2. Create Virtual Environment

#### Using venv (recommended)
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate

# Verify activation (should show .venv in prompt)
which python
```

#### Using conda
```bash
# Create conda environment
conda create -n developer-dashboard python=3.9

# Activate environment
conda activate developer-dashboard
```

### 3. Install Dependencies

```bash
# Upgrade pip (recommended)
pip install --upgrade pip

# Install project dependencies
pip install -r requirements.txt

# Verify installation
pip list
```

Expected packages:
```
Flask==2.3.2
python-dateutil==2.8.2
requests==2.31.0
```

### 4. GitHub Token Configuration

#### Create GitHub Personal Access Token

1. **Navigate to GitHub Settings**
   - Go to [GitHub.com](https://github.com)
   - Click your profile picture → Settings
   - In the left sidebar, click **Developer settings**
   - Click **Personal access tokens** → **Fine-grained tokens**

2. **Generate New Token**
   - Click **Generate new token**
   - Set **Token name**: `Developer Dashboard`
   - Set **Expiration**: 90 days (or as needed)
   - Set **Resource owner**: Your organization

3. **Configure Repository Access**
   - **Repository access**: Select repositories or All repositories
   - **Permissions**:
     - Contents: **Read**
     - Metadata: **Read**
     - Pull requests: **Read**
     - Issues: **Read** (optional)

4. **Generate and Copy Token**
   - Click **Generate token**
   - Copy the token immediately (you won't see it again)
   - Store it securely

#### Required Token Permissions
```json
{
  "repository_permissions": {
    "contents": "read",
    "metadata": "read",
    "pull_requests": "read",
    "issues": "read"
  }
}
```

### 5. Configuration File Setup

#### Create Configuration Directory
```bash
# Create data directory (if not exists)
mkdir -p data

# Create configuration file
touch data/github_data.json
```

#### Basic Configuration Template
```json
{
  "github_token": "github_pat_your_token_here",
  "organization": "your-organization-name",
  "$github_token_name": "github_metrics_token",
  "teams": [
    {
      "name": "Backend Team",
      "repositories": [
        "api-service",
        "user-service",
        "payment-service"
      ]
    },
    {
      "name": "Frontend Team",
      "repositories": [
        "web-app",
        "mobile-app",
        "admin-panel"
      ]
    }
  ]
}
```

#### Advanced Configuration Example
```json
{
  "github_token": "YOUR_GITHUB_TOKEN",
  "organization": "sample-org",
  "$github_token_name": "github_metrics_token",
  "teams": [
    {
      "name": "Rider Backend",
      "repositories": [
        "ridergateway",
        "rider-service",
        "notification-service"
      ]
    },
    {
      "name": "Driver Backend",
      "repositories": [
        "drivergateway",
        "driver-service",
        "location-service"
      ]
    },
    {
      "name": "Payment Team",
      "repositories": [
        "payment-service",
        "billing-service",
        "wallet-service"
      ]
    },
    {
      "name": "DevOps Team",
      "repositories": [
        "infrastructure",
        "deployment-scripts",
        "monitoring-tools"
      ]
    }
  ]
}
```

---

## 🔧 Environment Configuration

### Environment Variables (Optional)

Create a `.env` file for environment-specific configuration:

```bash
# Create .env file
touch .env
```

`.env` contents:
```env
# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
FLASK_PORT=5000

# GitHub Configuration
GITHUB_TOKEN=github_pat_your_token_here
GITHUB_ORGANIZATION=your-organization

# Cache Configuration
CACHE_TTL=43200  # 12 hours in seconds
CACHE_ENABLED=true

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=app.log
```

### Configuration Validation

Create a validation script to test your configuration:

```python
# config_test.py
import json
import os
import requests

def validate_config():
    """Validate GitHub configuration and token"""
    
    # Load configuration
    try:
        with open('data/github_data.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ Configuration file not found: data/github_data.json")
        return False
    
    # Validate required fields
    required_fields = ['github_token', 'organization', 'teams']
    for field in required_fields:
        if field not in config:
            print(f"❌ Missing required field: {field}")
            return False
    
    # Test GitHub token
    headers = {
        'Authorization': f'token {config["github_token"]}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    try:
        response = requests.get('https://api.github.com/user', headers=headers)
        if response.status_code == 200:
            user_data = response.json()
            print(f"✅ GitHub token valid - Authenticated as: {user_data['login']}")
        else:
            print(f"❌ GitHub token invalid - Status: {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"❌ GitHub API connection failed: {e}")
        return False
    
    # Test organization access
    try:
        org_url = f'https://api.github.com/orgs/{config["organization"]}'
        response = requests.get(org_url, headers=headers)
        if response.status_code == 200:
            org_data = response.json()
            print(f"✅ Organization access valid - {org_data['name']}")
        else:
            print(f"❌ Organization access failed - Status: {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"❌ Organization API connection failed: {e}")
        return False
    
    # Test repository access
    for team in config['teams']:
        print(f"\n🔍 Testing team: {team['name']}")
        for repo in team['repositories']:
            repo_url = f'https://api.github.com/repos/{config["organization"]}/{repo}'
            try:
                response = requests.get(repo_url, headers=headers)
                if response.status_code == 200:
                    print(f"  ✅ {repo} - accessible")
                else:
                    print(f"  ❌ {repo} - Status: {response.status_code}")
            except requests.RequestException:
                print(f"  ❌ {repo} - Connection failed")
    
    print("\n🎉 Configuration validation complete!")
    return True

if __name__ == "__main__":
    validate_config()
```

Run the validation:
```bash
python config_test.py
```

---

## 🏃 Running the Application

### Development Mode

```bash
# Activate virtual environment
source .venv/bin/activate

# Run Flask development server
python app.py

# Alternative: Using Flask CLI
export FLASK_APP=app.py
export FLASK_ENV=development
flask run --host=127.0.0.1 --port=5000 --debug
```

### Production Mode

```bash
# Install production server
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# With configuration file
gunicorn -c gunicorn.conf.py app:app
```

#### Gunicorn Configuration (`gunicorn.conf.py`)
```python
# gunicorn.conf.py
bind = "0.0.0.0:5000"
workers = 4
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
preload_app = True
timeout = 120
keepalive = 2
```

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 5000

# Run application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  dashboard:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
    environment:
      - FLASK_ENV=production
    restart: unless-stopped
```

---

## 🔍 Verification & Testing

### Application Health Check

```bash
# Test main endpoints
curl http://localhost:5000/
curl http://localhost:5000/github-metrics
curl http://localhost:5000/team-comparison

# Test API endpoints
curl http://localhost:5000/api/cache-stats
```

### Performance Testing

```bash
# Install testing tools
pip install pytest requests-mock

# Run basic performance test
python -c "
import time
import requests

start = time.time()
response = requests.get('http://localhost:5000/')
end = time.time()

print(f'Response time: {end - start:.2f}s')
print(f'Status code: {response.status_code}')
"
```

### Cache Validation

```bash
# Check cache statistics
curl http://localhost:5000/api/cache-stats | python -m json.tool
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Port Already in Use
```bash
# Find process using port 5000
lsof -i :5000

# Kill process
kill -9 <PID>

# Or use different port
python app.py --port 5001
```

#### 2. GitHub API Rate Limiting
```bash
# Check rate limit status
curl -H "Authorization: token YOUR_TOKEN" \
  https://api.github.com/rate_limit
```

#### 3. Virtual Environment Issues
```bash
# Recreate virtual environment
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 4. Configuration File Issues
```bash
# Validate JSON syntax
python -m json.tool data/github_data.json

# Check file permissions
ls -la data/github_data.json
```

### Debug Mode

Enable debug mode for detailed error messages:
```python
# In app.py
app.debug = True
app.run(debug=True)
```

### Logging Configuration

```python
# Add to app.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
```

---

## 🎯 Next Steps

After successful setup:

1. **📊 Access the Dashboard**: Navigate to http://localhost:5000
2. **👥 Configure Teams**: Add your teams and repositories
3. **📈 Explore Metrics**: View team performance and metrics
4. **🔄 Set Up Caching**: Configure cache settings for optimal performance
5. **📚 Read Documentation**: Check out the [metrics guide](metrics.md)

---

## 🆘 Support

If you encounter issues:

1. **📖 Check Documentation**: Review the [overview](overview.md) and [API docs](api.md)
2. **🐛 Report Issues**: Create an issue on GitHub
3. **💬 Community**: Join our community discussions
4. **📧 Contact**: Reach out to the maintainers

---

<div align="center">
  <strong>🎉 Setup Complete!</strong>
  <br>
  <em>Your Developer Dashboard is ready to use</em>
</div> 