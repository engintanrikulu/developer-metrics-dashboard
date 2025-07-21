"""
Dummy data for demo mode - realistic sample API responses
"""
from datetime import datetime, timedelta
import random

# Sample contributors for realistic data
CONTRIBUTORS = [
    {"login": "alice-dev", "name": "Alice Johnson"},
    {"login": "bob-smith", "name": "Bob Smith"}, 
    {"login": "charlie-wilson", "name": "Charlie Wilson"},
    {"login": "diana-chen", "name": "Diana Chen"},
    {"login": "eve-rodriguez", "name": "Eve Rodriguez"}
]

def generate_pr_data(repo_name, count=15):
    """Generate realistic PR data for a repository"""
    prs = []
    now = datetime.now()
    
    for i in range(count):
        contributor = random.choice(CONTRIBUTORS)
        created_date = now - timedelta(days=random.randint(1, 30))
        merged_date = created_date + timedelta(hours=random.randint(2, 48))
        
        pr = {
            "number": 1000 + i,
            "title": f"Fix issue #{random.randint(100, 999)} - {random.choice(['Add feature', 'Fix bug', 'Update docs', 'Refactor code', 'Improve performance'])}",
            "user": {
                "login": contributor["login"],
                "name": contributor["name"]
            },
            "created_at": created_date.isoformat() + "Z",
            "merged_at": merged_date.isoformat() + "Z",
            "html_url": f"https://github.com/sample-org/{repo_name}/pull/{1000 + i}",
            "state": "closed",
            "merged": True,
            "additions": random.randint(50, 500),
            "deletions": random.randint(10, 200),
            "changed_files": random.randint(1, 8)
        }
        prs.append(pr)
    
    return prs

def get_dummy_pull_requests(repo_name):
    """Get dummy pull requests for a repository"""
    # Different repositories have different activity levels
    repo_activity = {
        "frontend-app": 18,
        "admin-panel": 12,
        "user-dashboard": 15,
        "mobile-web": 10,
        "api-service": 20,
        "auth-service": 14,
        "user-service": 16,
        "notification-service": 8,
        "infrastructure": 6,
        "deployment-scripts": 4,
        "monitoring-tools": 7,
        "data-pipeline": 13,
        "analytics-service": 11,
        "ml-models": 9,
        "ios-app": 12,
        "android-app": 14,
        "react-native-shared": 8
    }
    
    pr_count = repo_activity.get(repo_name, 12)
    return generate_pr_data(repo_name, pr_count)

def get_dummy_pr_reviews(pr_number):
    """Get dummy reviews for a PR"""
    now = datetime.now()
    review_date = now - timedelta(hours=random.randint(1, 12))
    
    reviewers = ["alice-dev", "bob-smith", "charlie-wilson"]
    reviewer = random.choice(reviewers)
    
    return [
        {
            "id": random.randint(1000000, 9999999),
            "user": {
                "login": reviewer
            },
            "submitted_at": review_date.isoformat() + "Z",
            "state": "APPROVED"
        }
    ]

def get_dummy_pr_commits(pr_number, pr_created_at=None, pr_merged_at=None):
    """Get dummy commits for a PR"""
    now = datetime.now()
    
    # If PR dates are provided, ensure commit is between creation and merge
    if pr_created_at and pr_merged_at:
        try:
            created_dt = datetime.fromisoformat(pr_created_at.replace('Z', '+00:00'))
            merged_dt = datetime.fromisoformat(pr_merged_at.replace('Z', '+00:00'))
            
            # Generate commit date between creation and merge (closer to creation)
            # Make sure we have at least 1 hour between commit and merge for realistic timing
            time_diff = merged_dt - created_dt
            if time_diff.total_seconds() > 3600:  # More than 1 hour
                # Generate commit time that's 10-50% of the way from creation to merge
                commit_offset_ratio = random.uniform(0.1, 0.5)
                commit_offset = timedelta(seconds=int(time_diff.total_seconds() * commit_offset_ratio))
                commit_date = created_dt + commit_offset
            else:
                # For very short PRs, put commit closer to creation
                commit_offset = timedelta(minutes=random.randint(5, 30))
                commit_date = created_dt + commit_offset
        except Exception:
            # Fallback to original logic if date parsing fails
            commit_date = now - timedelta(hours=random.randint(24, 72))
    else:
        # Fallback to original logic if no PR dates provided
        commit_date = now - timedelta(hours=random.randint(24, 72))
    
    contributor = random.choice(CONTRIBUTORS)
    
    return [
        {
            "sha": f"abc123{random.randint(1000, 9999)}",
            "commit": {
                "author": {
                    "name": contributor["name"],
                    "email": f"{contributor['login']}@company.com",
                    "date": commit_date.isoformat() + "Z"
                },
                "message": f"Initial commit for PR #{pr_number}"
            }
        }
    ]

def get_dummy_rate_limit():
    """Get dummy rate limit data"""
    return {
        "rate": {
            "limit": 5000,
            "remaining": 4500,
            "reset": int((datetime.now() + timedelta(hours=1)).timestamp())
        }
    }

def get_dummy_user_data():
    """Get dummy authenticated user data"""
    return {
        "login": "demo-user",
        "name": "Demo User",
        "email": "demo@company.com",
        "company": "Sample Organization"
    }

def get_dummy_organization_data():
    """Get dummy organization data"""
    return {
        "login": "sample-org",
        "name": "Sample Organization",
        "description": "A sample organization for demo purposes",
        "public_repos": 25,
        "private_repos": 15
    }

def get_dummy_repository_data(repo_name):
    """Get dummy repository data"""
    return {
        "name": repo_name,
        "full_name": f"sample-org/{repo_name}",
        "description": f"Sample repository: {repo_name}",
        "private": False,
        "language": random.choice(["JavaScript", "Python", "TypeScript", "Java", "Go"]),
        "stargazers_count": random.randint(10, 100),
        "forks_count": random.randint(5, 50)
    }

# Pre-generated team metrics for consistent demo experience
DEMO_TEAM_METRICS = {
    "Frontend Team": {
        "total_prs": 55,
        "pr_throughput": 1.83,
        "avg_merge_time": 4.2,
        "avg_pr_size": 280
    },
    "Backend Team": {
        "total_prs": 58,
        "pr_throughput": 1.93,
        "avg_merge_time": 3.8,
        "avg_pr_size": 320
    },
    "DevOps Team": {
        "total_prs": 17,
        "pr_throughput": 0.57,
        "avg_merge_time": 6.1,
        "avg_pr_size": 450
    },
    "Data Team": {
        "total_prs": 33,
        "pr_throughput": 1.10,
        "avg_merge_time": 5.3,
        "avg_pr_size": 380
    },
    "Mobile Team": {
        "total_prs": 34,
        "pr_throughput": 1.13,
        "avg_merge_time": 4.8,
        "avg_pr_size": 260
    }
}

# Global contributor data for cross-team metrics
GLOBAL_CONTRIBUTORS = [
    {
        "username": "alice-dev",
        "total_prs": 32,
        "avg_pr_size": 285,
        "total_lines_changed": 9120,
        "teams": ["Frontend Team", "Backend Team"],
        "repositories": ["frontend-app", "api-service", "user-service"]
    },
    {
        "username": "bob-smith", 
        "total_prs": 28,
        "avg_pr_size": 340,
        "total_lines_changed": 9520,
        "teams": ["Backend Team", "DevOps Team"],
        "repositories": ["api-service", "infrastructure", "deployment-scripts"]
    },
    {
        "username": "charlie-wilson",
        "total_prs": 24,
        "avg_pr_size": 220,
        "total_lines_changed": 5280,
        "teams": ["Frontend Team", "Mobile Team"],
        "repositories": ["admin-panel", "ios-app", "android-app"]
    },
    {
        "username": "diana-chen",
        "total_prs": 22,
        "avg_pr_size": 410,
        "total_lines_changed": 9020,
        "teams": ["Data Team"],
        "repositories": ["data-pipeline", "analytics-service", "ml-models"]
    },
    {
        "username": "eve-rodriguez",
        "total_prs": 18,
        "avg_pr_size": 195,
        "total_lines_changed": 3510,
        "teams": ["Mobile Team", "Frontend Team"],
        "repositories": ["react-native-shared", "mobile-web"]
    }
] 