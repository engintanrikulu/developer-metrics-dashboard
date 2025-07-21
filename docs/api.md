# 🔌 API Documentation

## 🎯 Overview

The Developer Dashboard provides a comprehensive REST API for accessing GitHub metrics, team performance data, and cache management. All endpoints return JSON responses and support modern HTTP standards.

### Base URL
```
http://localhost:5000
```

### Authentication
The API uses GitHub Personal Access Tokens for authentication. Configure your token in `data/github_data.json`.

---

## 🌐 Web Routes

### Dashboard Routes

#### `GET /`
**Description**: Main dashboard homepage

**Response**: HTML template (dashboard.html)

**Features**:
- Overview of available features
- Navigation to GitHub metrics and team comparison
- Modern Sapphire Blue & Eggshell design

**Example**:
```bash
curl http://localhost:5000/
```

---

#### `GET /github`
**Description**: Redirect to GitHub metrics (backward compatibility)

**Response**: 302 Redirect to `/github-metrics`

**Example**:
```bash
curl -L http://localhost:5000/github
```

---

#### `GET /github-metrics`
**Description**: Team selection page

**Response**: HTML template (github_team_selection.html)

**Features**:
- List of configured teams
- Team selection interface
- Loading animations
- Team statistics cards

**Example**:
```bash
curl http://localhost:5000/github-metrics
```

---

#### `GET /github-metrics/<team_name>`
**Description**: Team-specific metrics dashboard

**Parameters**:
- `team_name` (string): URL-encoded team name
- `start_date` (optional, query): Start date filter (YYYY-MM-DD)
- `end_date` (optional, query): End date filter (YYYY-MM-DD)

**Response**: HTML template (github_metrics.html)

**Features**:
- Team metrics visualization
- Date range filtering
- PR contributor leaderboards
- Weekly activity charts
- Cache management

**Example**:
```bash
# Basic team metrics
curl http://localhost:5000/github-metrics/Backend%20Team

# With date filters
curl "http://localhost:5000/github-metrics/Backend%20Team?start_date=2025-01-01&end_date=2025-01-31"
```

---

#### `GET /team-comparison`
**Description**: Team comparison dashboard

**Response**: HTML template (team_comparison.html)

**Features**:
- Side-by-side team comparison
- Cross-team performance metrics
- Global user performance rankings
- Visual comparison charts

**Example**:
```bash
curl http://localhost:5000/team-comparison
```

---

## 🔧 API Endpoints

### Team Metrics API

#### `GET /api/github-metrics/<team_name>`
**Description**: Get team metrics in JSON format

**Parameters**:
- `team_name` (string): URL-encoded team name
- `start_date` (optional, query): Start date filter (YYYY-MM-DD)
- `end_date` (optional, query): End date filter (YYYY-MM-DD)

**Response**:
```json
{
  "team_name": "Backend Team",
  "metrics": [
    {
      "repository": "api-service",
      "pr_throughput": 1.2,
      "mr_time": 8.5,
      "first_commit_to_merge": 24.3,
      "total_prs": 18,
      "date_range": {
        "start": "2025-01-01",
        "end": "2025-01-31",
        "total_days": 31,
        "formatted_range": "Jan 1, 2025 - Jan 31, 2025"
      },
      "weekly_counts": [
        {
          "week": "2025-01-06",
          "week_label": "Jan 6",
          "total_prs": 5,
          "merged_prs": 4
        }
      ],
      "leaderboard": [
        {
          "username": "john_doe",
          "total_prs": 8,
          "total_lines_changed": 2340,
          "total_additions": 1890,
          "total_deletions": 450,
          "avg_pr_size": 293,
          "repositories": ["api-service"],
          "repositories_count": 1
        }
      ]
    }
  ],
  "team_leaderboard": [
    {
      "username": "john_doe",
      "total_prs": 15,
      "total_lines_changed": 4230,
      "total_additions": 3560,
      "total_deletions": 670,
      "avg_pr_size": 282,
      "repositories": ["api-service", "user-service"],
      "repositories_count": 2
    }
  ],
  "top_5_mr_times": [
    {
      "repository": "api-service",
      "pr_number": 123,
      "pr_title": "Add user authentication",
      "pr_url": "https://github.com/org/api-service/pull/123",
      "author": "john_doe",
      "created_at": "2025-01-15T10:00:00Z",
      "first_review_at": "2025-01-17T14:30:00Z",
      "mr_time_hours": 52.5
    }
  ]
}
```

**Example**:
```bash
curl http://localhost:5000/api/github-metrics/Backend%20Team
```

---

### Cache Management API

#### `GET /api/cache-stats`
**Description**: Get cache statistics and health information

**Response**:
```json
{
  "cache_stats": {
    "total_items": 42,
    "ttl_seconds": 43200,
    "cache_age_hours": 2.5
  },
  "cache_breakdown": {
    "repo_metrics": 8,
    "team_cache": 4,
    "prs": 12,
    "all_reviews": 6,
    "all_commits": 6,
    "detailed_prs": 6,
    "rate_limit": 1
  },
  "cache_health": {
    "hit_rate": 0.87,
    "miss_rate": 0.13,
    "eviction_count": 0
  }
}
```

**Example**:
```bash
curl http://localhost:5000/api/cache-stats
```

---

#### `POST /api/clear-cache/<team_name>`
**Description**: Clear cache for a specific team

**Parameters**:
- `team_name` (string): URL-encoded team name

**Response**:
```json
{
  "message": "Cache cleared successfully for team: Backend Team",
  "cleared_keys": [
    "Backend Team_last30PR",
    "Backend Team_month_2025-01",
    "repo_metrics_api-service",
    "repo_metrics_user-service"
  ],
  "timestamp": "2025-01-20T10:30:00Z"
}
```

**Example**:
```bash
curl -X POST http://localhost:5000/api/clear-cache/Backend%20Team
```

---

### Team Comparison API

#### `GET /api/team-comparison`
**Description**: Get team comparison data

**Response**:
```json
{
  "teams": [
    {
      "name": "Backend Team",
      "avg_pr_throughput": 1.2,
      "avg_mr_time": 8.5,
      "avg_commit_to_merge": 24.3,
      "total_prs": 45,
      "total_contributors": 6,
      "repositories": ["api-service", "user-service"],
      "repository_count": 2
    },
    {
      "name": "Frontend Team",
      "avg_pr_throughput": 1.8,
      "avg_mr_time": 6.2,
      "avg_commit_to_merge": 18.7,
      "total_prs": 62,
      "total_contributors": 4,
      "repositories": ["web-app", "mobile-app"],
      "repository_count": 2
    }
  ],
  "global_users": [
    {
      "username": "john_doe",
      "total_prs": 23,
      "total_lines_changed": 5670,
      "avg_pr_size": 247,
      "teams": ["Backend Team", "DevOps Team"],
      "team_count": 2,
      "repositories": ["api-service", "user-service", "deployment-scripts"],
      "repository_count": 3
    }
  ]
}
```

**Example**:
```bash
curl http://localhost:5000/api/team-comparison
```

---

### GitHub Rate Limit API

#### `GET /api/rate-limit`
**Description**: Get GitHub API rate limit status

**Response**:
```json
{
  "rate_limit": {
    "limit": 5000,
    "remaining": 4856,
    "reset": "2025-01-20T11:30:00Z",
    "used": 144,
    "percentage_used": 2.88
  },
  "status": "healthy",
  "requests_per_hour": 5000,
  "estimated_time_to_reset": "45 minutes"
}
```

**Example**:
```bash
curl http://localhost:5000/api/rate-limit
```

---

## 🔒 Error Handling

### Error Response Format

All API endpoints return consistent error responses:

```json
{
  "error": {
    "code": "TEAM_NOT_FOUND",
    "message": "Team 'Invalid Team' not found in configuration",
    "details": {
      "team_name": "Invalid Team",
      "available_teams": ["Backend Team", "Frontend Team"]
    }
  },
  "status": 404,
  "timestamp": "2025-01-20T10:30:00Z"
}
```

### Common Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `TEAM_NOT_FOUND` | 404 | Requested team not found in configuration |
| `INVALID_DATE_RANGE` | 400 | Invalid date range provided |
| `GITHUB_API_ERROR` | 502 | GitHub API is unavailable |
| `RATE_LIMIT_EXCEEDED` | 429 | GitHub API rate limit exceeded |
| `CACHE_ERROR` | 500 | Cache system error |
| `CONFIGURATION_ERROR` | 500 | Invalid configuration file |

---

## 🎯 Response Examples

### Team Metrics Response (Detailed)

```json
{
  "team_name": "Backend Team",
  "error": null,
  "metrics": [
    {
      "repository": "api-service",
      "pr_throughput": 1.2,
      "mr_time": 8.5,
      "first_commit_to_merge": 24.3,
      "total_prs": 18,
      "date_range": {
        "start": "2025-01-01",
        "end": "2025-01-31",
        "total_days": 31,
        "formatted_range": "Jan 1, 2025 - Jan 31, 2025",
        "has_data": true,
        "filter_description": "Custom range: Jan 1, 2025 - Jan 31, 2025"
      },
      "weekly_counts": [
        {
          "week": "2025-01-06",
          "week_label": "Jan 6",
          "total_prs": 5,
          "merged_prs": 4
        },
        {
          "week": "2025-01-13",
          "week_label": "Jan 13",
          "total_prs": 3,
          "merged_prs": 3
        },
        {
          "week": "2025-01-20",
          "week_label": "Jan 20",
          "total_prs": 4,
          "merged_prs": 3
        },
        {
          "week": "2025-01-27",
          "week_label": "Jan 27",
          "total_prs": 6,
          "merged_prs": 5
        }
      ],
      "weekly_total_created": 18,
      "weekly_total_merged": 15,
      "leaderboard": [
        {
          "username": "john_doe",
          "total_prs": 8,
          "total_lines_changed": 2340,
          "total_additions": 1890,
          "total_deletions": 450,
          "avg_pr_size": 293,
          "repositories": ["api-service"],
          "repositories_count": 1
        },
        {
          "username": "jane_smith",
          "total_prs": 5,
          "total_lines_changed": 1120,
          "total_additions": 890,
          "total_deletions": 230,
          "avg_pr_size": 224,
          "repositories": ["api-service"],
          "repositories_count": 1
        }
      ]
    }
  ],
  "team_leaderboard": [
    {
      "username": "john_doe",
      "total_prs": 15,
      "total_lines_changed": 4230,
      "total_additions": 3560,
      "total_deletions": 670,
      "avg_pr_size": 282,
      "repositories": ["api-service", "user-service"],
      "repositories_count": 2
    }
  ],
  "top_5_mr_times": [
    {
      "repository": "api-service",
      "pr_number": 123,
      "pr_title": "Add user authentication endpoint",
      "pr_url": "https://github.com/yourorg/api-service/pull/123",
      "author": "john_doe",
      "created_at": "2025-01-15T10:00:00Z",
      "first_review_at": "2025-01-17T14:30:00Z",
      "mr_time_hours": 52.5
    }
  ],
  "overall_date_range": {
    "start": "2025-01-01",
    "end": "2025-01-31",
    "total_days": 31,
    "formatted_range": "Jan 1, 2025 - Jan 31, 2025",
    "has_data": true,
    "filter_description": "Custom range: Jan 1, 2025 - Jan 31, 2025"
  },
  "chart_data_json": "..."
}
```

---

## 📊 Data Models

### Team Configuration

```json
{
  "name": "Backend Team",
  "repositories": [
    "api-service",
    "user-service",
    "payment-service"
  ]
}
```

### PR Metrics

```json
{
  "repository": "api-service",
  "pr_throughput": 1.2,
  "mr_time": 8.5,
  "first_commit_to_merge": 24.3,
  "total_prs": 18,
  "date_range": {
    "start": "2025-01-01",
    "end": "2025-01-31",
    "total_days": 31,
    "formatted_range": "Jan 1, 2025 - Jan 31, 2025"
  }
}
```

### Contributor Data

```json
{
  "username": "john_doe",
  "total_prs": 8,
  "total_lines_changed": 2340,
  "total_additions": 1890,
  "total_deletions": 450,
  "avg_pr_size": 293,
  "repositories": ["api-service"],
  "repositories_count": 1
}
```

### Weekly Activity

```json
{
  "week": "2025-01-06",
  "week_label": "Jan 6",
  "total_prs": 5,
  "merged_prs": 4
}
```

---

## 🔄 Caching Strategy

### Cache Keys

The API uses structured cache keys for optimal performance:

```
# Team metrics (default last 30 PRs)
{team_name}_last30PR

# Team metrics with date range
{team_name}_start_{start_date}_end_{end_date}

# Monthly team metrics
{team_name}_month_{year}-{month}

# Repository metrics
repo_metrics_{repository_name}

# Repository metrics with date range
repo_metrics_{repository_name}_start_{start_date}_end_{end_date}

# PR data
prs_{repository_name}_{count}

# PR data with date range
prs_{repository_name}_{count}_start_{start_date}_end_{end_date}

# Review data
all_reviews_{repository_name}

# Commit data
all_commits_{repository_name}

# Detailed PR data
detailed_prs_{repository_name}

# Rate limit
rate_limit
```

### Cache TTL (Time To Live)

- **Default TTL**: 43200 seconds (12 hours)
- **Rate Limit TTL**: 300 seconds (5 minutes)
- **Cache Strategy**: Last Recently Used (LRU)

### Cache Invalidation

Cache can be invalidated through:
1. **Automatic expiration** after TTL
2. **Manual clearing** via `/api/clear-cache/<team_name>`
3. **Application restart**

---

## 🛠️ Development Guidelines

### Adding New Endpoints

1. **Route Definition**: Add route in `app.py`
2. **Handler Function**: Implement business logic
3. **Response Format**: Use consistent JSON structure
4. **Error Handling**: Implement proper error responses
5. **Documentation**: Update this API documentation

### Testing API Endpoints

```bash
# Test with curl
curl -X GET http://localhost:5000/api/github-metrics/Backend%20Team

# Test with Python requests
import requests
response = requests.get('http://localhost:5000/api/github-metrics/Backend%20Team')
print(response.json())

# Test with Postman
# Import the provided Postman collection
```

### Performance Considerations

1. **Caching**: Implement appropriate caching for expensive operations
2. **Pagination**: Consider pagination for large datasets
3. **Rate Limiting**: Respect GitHub API rate limits
4. **Async Processing**: Use background tasks for long-running operations

---

## 🔐 Security Considerations

### Authentication

- **GitHub Token**: Secure token storage in configuration
- **Rate Limiting**: Respect GitHub API limits
- **Input Validation**: Validate all user inputs
- **Error Handling**: Don't expose sensitive information

### Best Practices

1. **HTTPS**: Use HTTPS in production
2. **CORS**: Configure Cross-Origin Resource Sharing
3. **Input Sanitization**: Sanitize all user inputs
4. **Error Messages**: Provide helpful but not revealing error messages

---

<div align="center">
  <strong>🔌 API Documentation</strong>
  <br>
  <em>Comprehensive API for GitHub metrics and team performance</em>
</div> 