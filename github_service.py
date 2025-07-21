import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import requests
from statistics import mean
import logging
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from functools import partial

# Import configuration and dummy data
import config
import dummy_data

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration constants (with fallbacks for backwards compatibility)
INITIAL_PR_FETCH_COUNT = getattr(config, 'INITIAL_PR_FETCH_COUNT', 20)
MAX_CONCURRENT_REQUESTS = getattr(config, 'MAX_CONCURRENT_REQUESTS', 8)
REQUEST_DELAY = getattr(config, 'REQUEST_DELAY', 0.1)

class MemoryCache:
    """Simple in-memory cache with expiration"""
    
    def __init__(self, default_ttl_seconds: int = 43200):  # 12 hours default
        self.cache = {}
        self.default_ttl = default_ttl_seconds
    
    def get(self, key: str) -> Any:
        """Get value from cache if not expired"""
        if key in self.cache:
            value, expiry_time = self.cache[key]
            if time.time() < expiry_time:
                logger.info(f"Cache HIT for key: {key}")
                return value
            else:
                # Expired, remove from cache
                del self.cache[key]
                logger.info(f"Cache EXPIRED for key: {key}")
        
        logger.info(f"Cache MISS for key: {key}")
        return None
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set value in cache with TTL"""
        ttl = ttl_seconds or self.default_ttl
        expiry_time = time.time() + ttl
        self.cache[key] = (value, expiry_time)
        logger.info(f"Cache SET for key: {key} (TTL: {ttl}s)")
    
    def clear(self) -> None:
        """Clear all cached data"""
        self.cache.clear()
        logger.info("Cache CLEARED")
    
    def clear_team_cache(self, team_name: str) -> int:
        """Clear all cache entries for a specific team"""
        cache_keys_to_clear = []
        
        # Find all cache keys for this team
        for key in self.cache.keys():
            if key.startswith(f"{team_name}_") or f"_{team_name}_" in key:
                cache_keys_to_clear.append(key)
        
        # Clear the keys
        for key in cache_keys_to_clear:
            if key in self.cache:
                del self.cache[key]
        
        logger.info(f"Cleared {len(cache_keys_to_clear)} cache entries for team: {team_name}")
        return len(cache_keys_to_clear)
    
    def size(self) -> int:
        """Get current cache size"""
        return len(self.cache)

class GitHubService:
    def __init__(self):
        self.config = self.load_config()
        self.token = self.config.get('github_token')
        self.organization = self.config.get('organization')
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Initialize cache (12 hours TTL)
        self.cache = MemoryCache(default_ttl_seconds=43200)
        
        # Log configuration for debugging
        logger.info(f"GitHub Service initialized:")
        if config.DEMO_MODE:
            logger.info("🎭 DEMO MODE ACTIVE - Using dummy data")
            logger.info(f"  Organization: {self.organization} (demo)")
            logger.info(f"  Token: {self.token} (demo)")
        else:
            logger.info(f"  Organization: {self.organization}")
            logger.info(f"  Token (first 7 chars): {self.token[:7] if self.token else 'None'}...")
            logger.info(f"  Token (last 4 chars): ...{self.token[-4:] if self.token else 'None'}")
        logger.info(f"  Cache initialized with 12-hour TTL")
        logger.info(f"  Headers: {dict(self.headers)}")
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from data/github_data.json"""
        try:
            with open('data/github_data.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError("data/github_data.json not found")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in data/github_data.json")
    
    def get_all_team_names(self) -> List[str]:
        """Get all team names from configuration"""
        teams = self.config.get('teams', [])
        return [team['name'] for team in teams]
    
    def get_team_repositories(self, team_name: str) -> List[str]:
        """Get repositories for a specific team"""
        teams = self.config.get('teams', [])
        for team in teams:
            if team.get('name') == team_name:
                return team.get('repositories', [])
        return []
    
    def _determine_cache_strategy(self, team_name: str, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Determine the appropriate cache strategy based on filter type"""
        if not start_date and not end_date:
            # No filter - use default last 20 PRs cache
            return {
                'strategy': 'default',
                'cache_key': f"{team_name}_last30PR",
                'should_cache': True
            }
        
        # Check if this is a quick month filter
        if start_date and end_date:
            month_info = self._is_quick_month_filter(start_date, end_date)
            if month_info:
                return {
                    'strategy': 'quick_month',
                    'cache_key': f"{team_name}_month_{month_info['year']}-{month_info['month']:02d}",
                    'should_cache': True,
                    'month_info': month_info
                }
        
        # Custom date range - no caching, but check if it fits within existing month cache
        existing_month_cache = self._find_month_cache_for_range(team_name, start_date, end_date)
        if existing_month_cache:
            return {
                'strategy': 'filter_from_month_cache',
                'cache_key': existing_month_cache['cache_key'],
                'should_cache': False,
                'filter_from_cache': True,
                'month_info': existing_month_cache['month_info']
            }
        
        return {
            'strategy': 'custom_date_range',
            'cache_key': None,
            'should_cache': False,
            'filter_from_cache': False
        }
    
    def _is_quick_month_filter(self, start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
        """Check if the date range represents a full month (quick month filter)"""
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            # Check if start date is the 1st of the month
            if start_dt.day != 1:
                return None
            
            # Check if end date is the last day of the same month
            # Get the last day of the month
            next_month = start_dt.replace(day=28) + timedelta(days=4)
            last_day_of_month = next_month - timedelta(days=next_month.day)
            
            if end_dt.date() == last_day_of_month.date():
                return {
                    'year': start_dt.year,
                    'month': start_dt.month,
                    'start_date': start_date,
                    'end_date': end_date
                }
        except ValueError:
            pass
        
        return None
    
    def _find_month_cache_for_range(self, team_name: str, start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
        """Find if there's an existing month cache that contains the given date range"""
        if not start_date or not end_date:
            return None
        
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            # Check if the range falls within a single month
            if start_dt.month == end_dt.month and start_dt.year == end_dt.year:
                month_cache_key = f"{team_name}_month_{start_dt.year}-{start_dt.month:02d}"
                
                # Check if this month cache exists
                if self.cache.get(month_cache_key) is not None:
                    return {
                        'cache_key': month_cache_key,
                        'month_info': {
                            'year': start_dt.year,
                            'month': start_dt.month
                        }
                    }
        except ValueError:
            pass
        
        return None
    
    def _filter_data_by_date_range(self, team_metrics: Dict[str, Any], start_date: str, end_date: str) -> Dict[str, Any]:
        """Filter cached team metrics data by date range"""
        filtered_metrics = []
        
        for metric in team_metrics.get('metrics', []):
            filtered_metric = dict(metric)
            
            # Filter PR data
            if 'pr_data' in metric:
                filtered_pr_data = []
                for pr in metric['pr_data']:
                    pr_date = datetime.strptime(pr['created_at'][:10], '%Y-%m-%d')
                    if start_date <= pr_date.strftime('%Y-%m-%d') <= end_date:
                        filtered_pr_data.append(pr)
                
                filtered_metric['pr_data'] = filtered_pr_data
                
                # Recalculate metrics based on filtered data
                filtered_metric['total_prs'] = len(filtered_pr_data)
                
                # Recalculate PR throughput (filtered PRs / 30 days)
                filtered_metric['pr_throughput'] = len([pr for pr in filtered_pr_data if pr.get('merged_at')]) / 30
                
                # Recalculate MR time and First commit to merge time
                # Note: These methods expect the original PR data structure from GitHub API
                # Since filtered_pr_data contains complete PR data, we need to transform it back
                filtered_prs_for_calculation = []
                for pr in filtered_pr_data:
                    # Transform back to the expected structure for these calculations
                    pr_for_calc = {
                        'created_at': pr['created_at'],
                        'merged_at': pr.get('merged_at'),
                        'number': pr.get('pr_number', 0),
                        'user': pr.get('user', {}),
                        'title': pr.get('pr_title', ''),
                        'html_url': pr.get('pr_url', '')
                    }
                    filtered_prs_for_calculation.append(pr_for_calc)
                
                filtered_metric['mr_time'], _ = self._calculate_mr_time_with_data(
                    filtered_prs_for_calculation,
                    filtered_metric['repository']
                )
                
                filtered_metric['first_commit_to_merge'] = self._calculate_first_commit_to_merge(
                    filtered_prs_for_calculation,
                    filtered_metric['repository']
                )
                
                # Recalculate weekly counts
                filtered_metric['weekly_counts'] = self._calculate_weekly_pr_counts(
                    [{'created_at': pr['created_at'], 'merged_at': pr.get('merged_at')} for pr in filtered_pr_data]
                )
                
                # Recalculate weekly totals
                filtered_metric['weekly_total_created'] = sum(week['total_prs'] for week in filtered_metric['weekly_counts']) if filtered_metric['weekly_counts'] else 0
                filtered_metric['weekly_total_merged'] = sum(week['merged_prs'] for week in filtered_metric['weekly_counts']) if filtered_metric['weekly_counts'] else 0
                
                # Recalculate leaderboard with complete PR data
                filtered_metric['leaderboard'] = self._calculate_pr_leaderboard(
                    filtered_pr_data,
                    filtered_metric['repository']
                )
                
                # Recalculate date range
                filtered_metric['date_range'] = self._calculate_date_range(filtered_pr_data)
            
            filtered_metrics.append(filtered_metric)
        
        # Update team metrics
        filtered_team_metrics = dict(team_metrics)
        filtered_team_metrics['metrics'] = filtered_metrics
        
        # Recalculate team leaderboard
        filtered_team_metrics['team_leaderboard'] = self._calculate_team_leaderboard(filtered_metrics)
        
        # Recalculate top 5 MR times with filtered data
        all_filtered_pr_data = []
        for metric in filtered_metrics:
            if metric.get('pr_data'):
                all_filtered_pr_data.extend(metric['pr_data'])
        
        filtered_team_metrics['top_5_mr_times'] = self.get_top_5_mr_times(all_filtered_pr_data)
        
        # Update overall date range
        all_prs = []
        for metric in filtered_metrics:
            if metric.get('pr_data'):
                for pr_data in metric['pr_data']:
                    all_prs.append({'created_at': pr_data['created_at']})
        
        filtered_team_metrics['overall_date_range'] = self._calculate_date_range(all_prs)
        
        # Add filter information
        filtered_team_metrics['overall_date_range'].update({
            'applied_start_date': start_date,
            'applied_end_date': end_date,
            'filter_description': self._format_filter_description(start_date, end_date)
        })
        
        return filtered_team_metrics
    
    def get_repo_metrics(self, repo_name: str, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Calculate metrics for a specific repository with optional date filtering"""
        # Create cache key for repository metrics with date range
        cache_key_parts = ["repo_metrics", repo_name]
        if start_date:
            cache_key_parts.append(f"start_{start_date}")
        if end_date:
            cache_key_parts.append(f"end_{end_date}")
        cache_key = "_".join(cache_key_parts)
        
        # Check cache first
        cached_metrics = self.cache.get(cache_key)
        if cached_metrics is not None:
            logger.info(f"Using cached metrics for repository: {repo_name} (date range: {start_date} to {end_date})")
            return cached_metrics
        
        logger.info(f"Calculating fresh metrics for repository: {repo_name} (date range: {start_date} to {end_date})")
        
        try:
            # Get pull requests with date filtering (use async version for better rate limiting)
            prs = self._get_recent_pull_requests_async(repo_name, days=30, start_date=start_date, end_date=end_date)
            
            # Calculate metrics
            pr_throughput = self._calculate_pr_throughput(prs)
            mr_time, pr_data = self._calculate_mr_time_with_data(prs, repo_name)
            first_commit_to_merge = self._calculate_first_commit_to_merge(prs, repo_name)
            
            # Calculate weekly PR counts
            weekly_counts = self._calculate_weekly_pr_counts(prs)
            
            # Calculate PR leaderboard
            leaderboard = self._calculate_pr_leaderboard(prs, repo_name)
            
            # Calculate date range
            date_range = self._calculate_date_range(prs)
            
            # Calculate weekly totals for easier template display
            weekly_total_created = sum(week['total_prs'] for week in weekly_counts) if weekly_counts else 0
            weekly_total_merged = sum(week['merged_prs'] for week in weekly_counts) if weekly_counts else 0
            
            metrics_result = {
                'repository': repo_name,
                'pr_throughput': pr_throughput,
                'mr_time': mr_time,
                'first_commit_to_merge': first_commit_to_merge,
                'total_prs': len(prs),
                'pr_data': pr_data,  # Store PR data for top 5 analysis
                'weekly_counts': weekly_counts,
                'weekly_total_created': weekly_total_created,
                'weekly_total_merged': weekly_total_merged,
                'leaderboard': leaderboard,
                'date_range': date_range
            }
            
            # Cache the result for 12 hours
            self.cache.set(cache_key, metrics_result)
            logger.info(f"Cached metrics for repository: {repo_name} with key: {cache_key}")
            
            return metrics_result
            
        except Exception as e:
            logger.error(f"Error calculating metrics for {repo_name}: {e}")
            error_result = {
                'repository': repo_name,
                'pr_throughput': 0,
                'mr_time': 0,
                'first_commit_to_merge': 0,
                'total_prs': 0,
                'pr_data': [],
                'weekly_counts': [],
                'weekly_total_created': 0,
                'weekly_total_merged': 0,
                'leaderboard': [],
                'date_range': {
                    'start_date': None,
                    'end_date': None,
                    'formatted_range': 'No data available due to error',
                    'has_data': False
                },
                'error': str(e)
            }
            
            # Cache error result for shorter time (5 minutes)
            self.cache.set(cache_key, error_result, ttl_seconds=300)
            logger.info(f"Cached error result for repository: {repo_name}")
            
            return error_result
    
    def get_all_team_metrics(self, team_name: str, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Get metrics for all repositories in a team with optional date filtering"""
        # Determine cache strategy
        cache_strategy = self._determine_cache_strategy(team_name, start_date, end_date)
        logger.info(f"Cache strategy for {team_name}: {cache_strategy['strategy']}")
        
        # Try to get cached data first
        if cache_strategy['cache_key']:
            cached_team_metrics = self.cache.get(cache_strategy['cache_key'])
            if cached_team_metrics is not None:
                logger.info(f"Using cached team metrics for: {team_name} (cache key: {cache_strategy['cache_key']})")
                
                # If we need to filter from cached data
                if cache_strategy.get('filter_from_cache') and start_date and end_date:
                    logger.info(f"Filtering cached data for date range: {start_date} to {end_date}")
                    return self._filter_data_by_date_range(cached_team_metrics, start_date, end_date)
                
                return cached_team_metrics
        
        # Calculate fresh metrics
        logger.info(f"Calculating fresh team metrics for: {team_name} (date range: {start_date} to {end_date})")
        
        repositories = self.get_team_repositories(team_name)
        logger.info(f"Getting metrics for team '{team_name}' with repositories: {repositories}")
        
        # Check rate limit first
        self.check_rate_limit()
        
        # Test API access first
        self.test_api_access()
        
        metrics = []
        all_pr_data = []  # Store all PR data for top 5 analysis
        
        # For team-based caching, we need to determine the appropriate date range for repo metrics
        repo_start_date = start_date
        repo_end_date = end_date
        
        # For default strategy, we fetch all data and may filter later
        if cache_strategy['strategy'] == 'default':
            # For default strategy, don't pass date filters to repo metrics
            repo_start_date = None
            repo_end_date = None
        
        # Parallel processing of repositories
        metrics = self._fetch_repositories_parallel(repositories, repo_start_date, repo_end_date)
        
        # Store PR data for top 5 analysis
        for repo_metrics in metrics:
            if 'pr_data' in repo_metrics:
                all_pr_data.extend(repo_metrics['pr_data'])
        
        # Calculate top 5 highest MR times
        top_5_mr_times = self.get_top_5_mr_times(all_pr_data)
        
        # Calculate team-level leaderboard
        team_leaderboard = self._calculate_team_leaderboard(metrics)
        
        # Calculate overall date range across all repositories
        all_prs = []
        for metric in metrics:
            if metric.get('pr_data'):
                for pr_data in metric['pr_data']:
                    all_prs.append({'created_at': pr_data['created_at']})
        
        overall_date_range = self._calculate_date_range(all_prs)
        
        # Add applied filter information to date range
        if start_date or end_date:
            filter_info = {
                'applied_start_date': start_date,
                'applied_end_date': end_date,
                'filter_description': self._format_filter_description(start_date, end_date)
            }
            overall_date_range.update(filter_info)
        
        team_metrics_result = {
            'metrics': metrics,
            'top_5_mr_times': top_5_mr_times,
            'team_leaderboard': team_leaderboard,
            'overall_date_range': overall_date_range,
            'applied_filters': {
                'start_date': start_date,
                'end_date': end_date
            }
        }
        
        # Cache the result if strategy allows
        if cache_strategy['should_cache'] and cache_strategy['cache_key']:
            self.cache.set(cache_strategy['cache_key'], team_metrics_result)
            logger.info(f"Cached team metrics for: {team_name} with key: {cache_strategy['cache_key']}")
        else:
            logger.info(f"Not caching team metrics for: {team_name} (strategy: {cache_strategy['strategy']})")
        
        return team_metrics_result
    
    def _fetch_repositories_parallel(self, repositories: List[str], start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """Fetch repository metrics in parallel using ThreadPoolExecutor"""
        if not repositories:
            return []
        
        logger.info(f"Fetching metrics for {len(repositories)} repositories in parallel (max {MAX_CONCURRENT_REQUESTS} concurrent)")
        
        metrics = []
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
            # Submit all repository tasks
            future_to_repo = {
                executor.submit(self.get_repo_metrics, repo, start_date, end_date): repo
                for repo in repositories
            }
            
            # Process completed tasks as they finish
            for future in as_completed(future_to_repo):
                repo_name = future_to_repo[future]
                try:
                    repo_metrics = future.result()
                    metrics.append(repo_metrics)
                    logger.info(f"Completed metrics for repository: {repo_name}")
                except Exception as e:
                    logger.error(f"Error fetching metrics for repository {repo_name}: {e}")
                    # Add error result to maintain repository order
                    error_result = {
                        'repository': repo_name,
                        'pr_throughput': 0,
                        'mr_time': 0,
                        'first_commit_to_merge': 0,
                        'total_prs': 0,
                        'pr_data': [],
                        'weekly_counts': [],
                        'weekly_total_created': 0,
                        'weekly_total_merged': 0,
                        'leaderboard': [],
                        'date_range': {
                            'start_date': None,
                            'end_date': None,
                            'formatted_range': 'Error fetching data',
                            'has_data': False
                        },
                        'error': str(e)
                    }
                    metrics.append(error_result)
        
        # Sort results to maintain original repository order
        repo_order = {repo: i for i, repo in enumerate(repositories)}
        metrics.sort(key=lambda x: repo_order.get(x['repository'], 999))
        
        logger.info(f"Completed parallel fetch for {len(metrics)} repositories")
        return metrics
    
    def _fetch_pr_data_parallel(self, repo_name: str, pr_numbers: List[int], merged_prs: List[Dict[str, Any]]) -> tuple[Dict[int, List[Dict[str, Any]]], List[Dict[str, Any]]]:
        """Fetch PR reviews and detailed PR data in parallel"""
        if not pr_numbers:
            return {}, []
        
        logger.info(f"Fetching PR data for {len(pr_numbers)} PRs in {repo_name} in parallel")
        
        # Create tasks for parallel execution
        all_reviews = {}
        detailed_pr_data = []
        
        # Use ThreadPoolExecutor for parallel API calls
        with ThreadPoolExecutor(max_workers=min(MAX_CONCURRENT_REQUESTS, 4)) as executor:
            # Submit reviews and detailed PR data tasks
            future_to_task = {}
            
            # Add reviews task
            future_to_task[executor.submit(self._get_all_pr_reviews, repo_name, pr_numbers)] = 'reviews'
            
            # Add detailed PR data task
            future_to_task[executor.submit(self._get_detailed_pr_data, merged_prs, repo_name)] = 'detailed_prs'
            
            # Process completed tasks
            for future in as_completed(future_to_task):
                task_type = future_to_task[future]
                try:
                    if task_type == 'reviews':
                        all_reviews = future.result()
                        logger.info(f"Completed reviews fetch for {repo_name}")
                    elif task_type == 'detailed_prs':
                        detailed_pr_data = future.result()
                        logger.info(f"Completed detailed PR data fetch for {repo_name}")
                except Exception as e:
                    logger.error(f"Error fetching {task_type} for {repo_name}: {e}")
                    if task_type == 'reviews':
                        all_reviews = {}
                    elif task_type == 'detailed_prs':
                        detailed_pr_data = []
                
                # Add small delay to avoid rate limiting
                time.sleep(REQUEST_DELAY)
        
        return all_reviews, detailed_pr_data
    
    def _get_recent_pull_requests_async(self, repo_name: str, days: int = 30, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """Async version of _get_recent_pull_requests with better rate limiting"""
        # Create cache key with date range
        cache_key_parts = ["prs", repo_name, str(days)]
        if start_date:
            cache_key_parts.append(f"start_{start_date}")
        if end_date:
            cache_key_parts.append(f"end_{end_date}")
        cache_key = "_".join(cache_key_parts)
        
        # Check cache first
        cached_prs = self.cache.get(cache_key)
        if cached_prs is not None:
            return cached_prs
        
        # Return dummy data if in demo mode
        if config.DEMO_MODE:
            logger.info(f"🎭 DEMO MODE: Returning dummy PR data for {repo_name}")
            dummy_prs = dummy_data.get_dummy_pull_requests(repo_name)
            # Cache dummy data
            self.cache.set(cache_key, dummy_prs)
            return dummy_prs
        
        # Calculate since date based on start_date or default days
        if start_date:
            since_date = start_date
        else:
            since_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        url = f"https://api.github.com/repos/{self.organization}/{repo_name}/pulls"
        
        params = {
            'state': 'closed',  # Only get closed PRs (merged or closed)
            'sort': 'updated',
            'direction': 'desc',
            'per_page': INITIAL_PR_FETCH_COUNT,  # Use configurable constant
            'since': since_date
        }
        
        logger.info(f"Fetching PRs for {repo_name} async (cache miss):")
        logger.info(f"  URL: {url}")
        logger.info(f"  Params: {params}")
        
        prs = []
        page = 1
        
        while True:
            params['page'] = page
            
            # Enhanced rate limiting with exponential backoff
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    # Add progressive delay based on page number
                    delay = REQUEST_DELAY * (page * 0.5)  # Increase delay for later pages
                    time.sleep(delay)
                    
                    response = requests.get(url, headers=self.headers, params=params)
                    
                    logger.info(f"  API Response for {repo_name} (page {page}): {response.status_code}")
                    
                    if response.status_code == 200:
                        break
                    elif response.status_code == 403:
                        # Rate limit hit - wait longer
                        wait_time = 2 ** retry_count  # Exponential backoff
                        logger.warning(f"Rate limit hit for {repo_name}, waiting {wait_time}s")
                        time.sleep(wait_time)
                        retry_count += 1
                    else:
                        logger.error(f"Error fetching PRs for {repo_name}: {response.status_code}")
                        logger.error(f"  Response text: {response.text}")
                        # Cache empty result for failed requests (shorter TTL)
                        self.cache.set(cache_key, [], ttl_seconds=300)  # 5 minutes for errors
                        return []
                        
                except Exception as e:
                    logger.error(f"Exception fetching PRs for {repo_name}: {e}")
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(2 ** retry_count)
                    else:
                        self.cache.set(cache_key, [], ttl_seconds=300)
                        return []
            
            if retry_count >= max_retries:
                logger.error(f"Max retries exceeded for {repo_name}")
                self.cache.set(cache_key, [], ttl_seconds=300)
                return []
            
            page_prs = response.json()
            if not page_prs:
                break
            
            # Filter PRs by date range if specified
            filtered_prs = []
            for pr in page_prs:
                created_at = pr['created_at']
                
                # Check if PR is within date range
                if start_date and created_at < start_date:
                    continue
                if end_date and created_at > end_date:
                    continue
                
                filtered_prs.append(pr)
            
            prs.extend(filtered_prs)
            
            # Stop if we've gone beyond our date range
            if page_prs[-1]['updated_at'] < since_date:
                break
                
            page += 1
            if page > 2:  # Keep reduced limit for faster responses
                break
        
        # Cache the result
        self.cache.set(cache_key, prs)
        logger.info(f"Cached {len(prs)} PRs for {repo_name} (async)")
        
        # Debug: Show some PR info
        if prs:
            logger.info(f"Sample PR dates for {repo_name}:")
            for i, pr in enumerate(prs[:3]):  # Show first 3 PRs
                logger.info(f"  PR #{pr['number']}: created {pr['created_at']}, merged {pr.get('merged_at', 'Not merged')}")
        
        return prs
    
    def get_all_teams_metrics(self, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Get metrics for all teams with optional date filtering"""
        logger.info(f"Getting metrics for all teams (date range: {start_date} to {end_date})")
        
        all_teams = self.get_all_team_names()
        teams_data = []
        
        for team_name in all_teams:
            try:
                team_metrics = self.get_all_team_metrics(team_name, start_date=start_date, end_date=end_date)
                
                # Calculate aggregate metrics for the team
                team_summary = self._calculate_team_summary(team_metrics, team_name)
                teams_data.append(team_summary)
                
                logger.info(f"Successfully fetched metrics for team: {team_name}")
            except Exception as e:
                logger.error(f"Error fetching metrics for team {team_name}: {e}")
                # Add error team data
                teams_data.append({
                    'team_name': team_name,
                    'pr_throughput': 0,
                    'avg_merge_time': 0,
                    'avg_pr_size': 0,
                    'total_merged_prs': 0,
                    'last_updated': None,
                    'error': str(e)
                })
        
        return {
            'teams': teams_data,
            'total_teams': len(all_teams),
            'last_updated': datetime.now().isoformat()
        }
    
    def _calculate_team_summary(self, team_metrics: Dict[str, Any], team_name: str) -> Dict[str, Any]:
        """Calculate summary metrics for a team"""
        metrics = team_metrics.get('metrics', [])
        
        if not metrics:
            return {
                'team_name': team_name,
                'pr_throughput': 0,
                'avg_merge_time': 0,
                'avg_pr_size': 0,
                'total_merged_prs': 0,
                'last_updated': datetime.now().isoformat(),
                'repositories_count': 0,
                'repositories': []
            }
        
        # Calculate aggregate metrics
        total_pr_throughput = sum(metric.get('pr_throughput', 0) for metric in metrics)
        avg_merge_times = [metric.get('mr_time', 0) for metric in metrics if metric.get('mr_time') is not None and metric.get('mr_time', 0) > 0]
        avg_merge_time = mean(avg_merge_times) if avg_merge_times else 0
        
        # Calculate average PR size from all PR data
        all_pr_sizes = []
        total_merged_prs = 0
        
        for metric in metrics:
            if metric.get('pr_data'):
                for pr in metric['pr_data']:
                    if pr.get('merged_at'):
                        total_merged_prs += 1
                        # Try to get PR size from detailed data, fallback to 0
                        pr_size = pr.get('additions', 0) + pr.get('deletions', 0)
                        if pr_size > 0:
                            all_pr_sizes.append(pr_size)
        
        avg_pr_size = mean(all_pr_sizes) if all_pr_sizes else 0
        
        # Get repository information
        repositories = [metric.get('repository', 'Unknown') for metric in metrics]
        
        # Try to get cache timestamp from team metrics
        cache_key = f"{team_name}_last30PR"
        cached_data = self.cache.get(cache_key)
        last_updated = datetime.now().isoformat()
        
        return {
            'team_name': team_name,
            'pr_throughput': round(total_pr_throughput, 2),
            'avg_merge_time': round(avg_merge_time, 2),
            'avg_pr_size': round(avg_pr_size, 0),
            'total_merged_prs': total_merged_prs,
            'last_updated': last_updated,
            'repositories_count': len(repositories),
            'repositories': repositories,
            'date_range': team_metrics.get('overall_date_range', {})
        }
    
    def check_rate_limit(self):
        """Check GitHub API rate limit before making calls"""
        # Create cache key for rate limit (shorter TTL)
        cache_key = "rate_limit"
        
        # Check cache first (5 minute TTL for rate limit)
        cached_rate_data = self.cache.get(cache_key)
        if cached_rate_data is not None:
            logger.info("Using cached rate limit data")
            self._log_rate_limit_info(cached_rate_data)
            return
        
        # Return dummy data if in demo mode
        if config.DEMO_MODE:
            logger.info("🎭 DEMO MODE: Returning dummy rate limit data")
            rate_data = dummy_data.get_dummy_rate_limit()
            self.cache.set(cache_key, rate_data, ttl_seconds=300)
            self._log_rate_limit_info(rate_data)
            return
        
        logger.info("Checking GitHub API rate limit...")
        
        url = "https://api.github.com/rate_limit"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            logger.error(f"Failed to check rate limit: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return
        
        rate_data = response.json()
        
        # Cache rate limit data for 5 minutes
        self.cache.set(cache_key, rate_data, ttl_seconds=300)
        
        self._log_rate_limit_info(rate_data)
    
    def _log_rate_limit_info(self, rate_data: Dict[str, Any]):
        """Log rate limit information"""
        rate_info = rate_data.get('rate', {})
        
        limit = rate_info.get('limit', 0)
        remaining = rate_info.get('remaining', 0)
        reset_timestamp = rate_info.get('reset', 0)
        
        # Convert reset timestamp to human-readable format
        if reset_timestamp:
            reset_time = datetime.fromtimestamp(reset_timestamp)
            reset_time_str = reset_time.strftime('%Y-%m-%d %H:%M:%S')
        else:
            reset_time_str = 'Unknown'
        
        logger.info(f"GitHub API Rate Limit Status:")
        logger.info(f"  Total limit: {limit}")
        logger.info(f"  Remaining requests: {remaining}")
        logger.info(f"  Reset time: {reset_time_str}")
        
        # Check if rate limit is exceeded
        if remaining == 0:
            logger.warning(f"⚠️ GitHub API rate limit exceeded. Resets at {reset_time_str}")
        elif remaining < 10:
            logger.warning(f"⚠️ GitHub API rate limit running low: {remaining} requests remaining")
    
    def test_api_access(self):
        """Test basic API access and authentication"""
        logger.info("Testing GitHub API access...")
        
        # Return dummy data if in demo mode
        if config.DEMO_MODE:
            logger.info("🎭 DEMO MODE: Simulating API access tests")
            
            # Simulate user authentication
            user_data = dummy_data.get_dummy_user_data()
            logger.info(f"  User API test: 200 (demo)")
            logger.info(f"  Authenticated as: {user_data.get('login', 'Unknown')} (demo)")
            
            # Simulate organization access
            if self.organization:
                org_data = dummy_data.get_dummy_organization_data()
                logger.info(f"  Organization API test: 200 (demo)")
                logger.info(f"  Organization: {org_data.get('name', 'Unknown')} ({org_data.get('login', 'Unknown')}) (demo)")
            
            # Simulate repository access
            team_names = self.get_all_team_names()
            if team_names:
                repositories = self.get_team_repositories(team_names[0])
                if repositories:
                    test_repo = repositories[0]
                    repo_data = dummy_data.get_dummy_repository_data(test_repo)
                    logger.info(f"  Repository '{test_repo}' API test: 200 (demo)")
                    logger.info(f"  Repository access: {repo_data.get('full_name', 'Unknown')} (private: {repo_data.get('private', 'Unknown')}) (demo)")
            return
        
        # Test user authentication
        url = "https://api.github.com/user"
        response = requests.get(url, headers=self.headers)
        logger.info(f"  User API test: {response.status_code}")
        
        if response.status_code == 200:
            user_data = response.json()
            logger.info(f"  Authenticated as: {user_data.get('login', 'Unknown')}")
        else:
            logger.error(f"  User API error: {response.text}")
        
        # Test organization access
        if self.organization:
            org_url = f"https://api.github.com/orgs/{self.organization}"
            org_response = requests.get(org_url, headers=self.headers)
            logger.info(f"  Organization API test: {org_response.status_code}")
            
            if org_response.status_code == 200:
                org_data = org_response.json()
                logger.info(f"  Organization: {org_data.get('name', 'Unknown')} ({org_data.get('login', 'Unknown')})")
            else:
                logger.error(f"  Organization API error: {org_response.text}")
        
        # Test repository access for first repo from first team
        team_names = self.get_all_team_names()
        if team_names:
            repositories = self.get_team_repositories(team_names[0])
            if repositories:
                test_repo = repositories[0]
                repo_url = f"https://api.github.com/repos/{self.organization}/{test_repo}"
                repo_response = requests.get(repo_url, headers=self.headers)
                logger.info(f"  Repository '{test_repo}' API test: {repo_response.status_code}")
                
                if repo_response.status_code == 200:
                    repo_data = repo_response.json()
                    logger.info(f"  Repository access: {repo_data.get('full_name', 'Unknown')} (private: {repo_data.get('private', 'Unknown')})")
                else:
                    logger.error(f"  Repository API error: {repo_response.text}")
    
    def _get_recent_pull_requests(self, repo_name: str, days: int = 30, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """Get pull requests from the last N days or within a specific date range"""
        # Create cache key with date range
        cache_key_parts = ["prs", repo_name, str(days)]
        if start_date:
            cache_key_parts.append(f"start_{start_date}")
        if end_date:
            cache_key_parts.append(f"end_{end_date}")
        cache_key = "_".join(cache_key_parts)
        
        # Check cache first
        cached_prs = self.cache.get(cache_key)
        if cached_prs is not None:
            return cached_prs
        
        # Calculate since date based on start_date or default days
        if start_date:
            since_date = start_date
        else:
            since_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        url = f"https://api.github.com/repos/{self.organization}/{repo_name}/pulls"
        
        params = {
            'state': 'closed',  # Only get closed PRs (merged or closed)
            'sort': 'updated',
            'direction': 'desc',
            'per_page': INITIAL_PR_FETCH_COUNT,  # Use configurable constant
            'since': since_date
        }
        
        logger.info(f"Fetching PRs for {repo_name} (cache miss):")
        logger.info(f"  URL: {url}")
        logger.info(f"  Params: {params}")
        
        prs = []
        page = 1
        
        while True:
            params['page'] = page
            
            # Add rate limiting delay
            time.sleep(REQUEST_DELAY)
            
            response = requests.get(url, headers=self.headers, params=params)
            
            logger.info(f"  API Response for {repo_name} (page {page}): {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Error fetching PRs for {repo_name}: {response.status_code}")
                logger.error(f"  Response text: {response.text}")
                print(f"Error fetching PRs for {repo_name}: {response.status_code}")
                # Cache empty result for failed requests (shorter TTL)
                self.cache.set(cache_key, [], ttl_seconds=300)  # 5 minutes for errors
                break
            
            page_prs = response.json()
            if not page_prs:
                break
            
            # Filter PRs by date range if specified
            filtered_prs = []
            for pr in page_prs:
                created_at = pr['created_at']
                
                # Check if PR is within date range
                if start_date and created_at < start_date:
                    continue
                if end_date and created_at > end_date:
                    continue
                
                filtered_prs.append(pr)
            
            prs.extend(filtered_prs)
            
            # Stop if we've gone beyond our date range
            if page_prs[-1]['updated_at'] < since_date:
                break
                
            page += 1
            if page > 2:  # Further reduced limit for faster responses with configurable count
                break
        
        # Cache the result
        self.cache.set(cache_key, prs)
        logger.info(f"Cached {len(prs)} PRs for {repo_name}")
        
        # Debug: Show some PR info
        if prs:
            logger.info(f"Sample PR dates for {repo_name}:")
            for i, pr in enumerate(prs[:3]):  # Show first 3 PRs
                logger.info(f"  PR #{pr['number']}: created {pr['created_at']}, merged {pr.get('merged_at', 'Not merged')}")
        
        return prs
    
    def _calculate_pr_throughput(self, prs: List[Dict[str, Any]]) -> float:
        """Calculate PR throughput (daily average merged PRs)"""
        if not prs:
            return 0
        
        merged_prs = [pr for pr in prs if pr['merged_at']]
        if not merged_prs:
            return 0
        
        # Calculate daily average over the last 30 days
        return len(merged_prs) / 30
    
    def _calculate_mr_time(self, prs: List[Dict[str, Any]]) -> float:
        """Calculate MR time (PR created_at → first review submitted_at) in hours"""
        if not prs:
            return 0
        
        mr_times = []
        
        for pr in prs:
            if not pr.get('merged_at'):
                continue
                
            try:
                # Get reviews for this PR
                reviews = self._get_pr_reviews(pr['number'], pr['head']['repo']['name'])
                if not reviews:
                    continue
                
                created_at = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))
                first_review_at = datetime.fromisoformat(reviews[0]['submitted_at'].replace('Z', '+00:00'))
                
                mr_time_hours = (first_review_at - created_at).total_seconds() / 3600
                mr_times.append(mr_time_hours)
                
            except Exception as e:
                print(f"Error calculating MR time for PR #{pr['number']}: {e}")
                continue
        
        return mean(mr_times) if mr_times else 0
    
    def _calculate_mr_time_with_data(self, prs: List[Dict[str, Any]], repo_name: str) -> tuple[float, List[Dict[str, Any]]]:
        """Calculate MR time and return PR data for top 5 analysis"""
        if not prs:
            return 0, []
        
        # Get all merged PRs
        merged_prs = [pr for pr in prs if pr.get('merged_at')]
        if not merged_prs:
            return 0, []
        
        # Extract PR numbers
        pr_numbers = [pr['number'] for pr in merged_prs]
        
        # Parallel fetch all required data
        all_reviews, detailed_pr_data = self._fetch_pr_data_parallel(repo_name, pr_numbers, merged_prs)
        detailed_pr_lookup = {pr['number']: pr for pr in detailed_pr_data}
        
        mr_times = []
        pr_data = []
        
        for pr in merged_prs:
            try:
                # Get reviews for this PR from batch data
                reviews = all_reviews.get(pr['number'], [])
                
                # Get detailed PR data for this PR
                detailed_pr = detailed_pr_lookup.get(pr['number'], pr)
                
                # Always include PR data for global user metrics, even if no reviews
                pr_data_entry = {
                    'repository': repo_name,
                    'pr_number': pr['number'],
                    'pr_title': pr['title'],
                    'pr_url': pr['html_url'],
                    'created_at': pr['created_at'],
                    'merged_at': pr['merged_at'],
                    'author': pr['user']['login'],
                    'additions': detailed_pr.get('additions', 0),
                    'deletions': detailed_pr.get('deletions', 0),
                    'total_lines_changed': detailed_pr.get('additions', 0) + detailed_pr.get('deletions', 0)
                }
                
                # Add review-specific data if reviews exist
                if reviews:
                    created_at = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))
                    first_review_at = datetime.fromisoformat(reviews[0]['submitted_at'].replace('Z', '+00:00'))
                    
                    mr_time_hours = (first_review_at - created_at).total_seconds() / 3600
                    mr_times.append(mr_time_hours)
                    
                    pr_data_entry['first_review_at'] = reviews[0]['submitted_at']
                    pr_data_entry['mr_time_hours'] = mr_time_hours
                else:
                    # No reviews - set review-specific fields to null
                    pr_data_entry['first_review_at'] = None
                    pr_data_entry['mr_time_hours'] = None
                
                pr_data.append(pr_data_entry)
                
            except Exception as e:
                logger.error(f"Error calculating MR time for PR #{pr['number']}: {e}")
                continue
        
        return mean(mr_times) if mr_times else 0, pr_data
    
    def get_top_5_mr_times(self, all_pr_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get top 5 highest MR times across all repositories"""
        if not all_pr_data:
            return []
        
        # Filter out PRs without MR time (PRs with no reviews) and sort by MR time (highest first)
        prs_with_mr_time = [pr for pr in all_pr_data if pr.get('mr_time_hours') is not None]
        sorted_prs = sorted(prs_with_mr_time, key=lambda x: x['mr_time_hours'], reverse=True)
        top_5 = sorted_prs[:5]
        
        logger.info(f"Top 5 highest MR times calculated: {len(top_5)} items")
        
        return top_5
    
    def _calculate_weekly_pr_counts(self, prs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Calculate weekly PR counts for the last 4 weeks"""
        if not prs:
            logger.info("No PRs provided for weekly calculation")
            return []
        
        logger.info(f"Calculating weekly PR counts for {len(prs)} PRs")
        
        # Group PRs by week
        weekly_data = {}
        today = datetime.now()
        
        for pr in prs:
            try:
                created_date = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))
                # Get the start of the week (Monday)
                week_start = created_date - timedelta(days=created_date.weekday())
                week_key = week_start.strftime('%Y-%m-%d')
                
                logger.debug(f"PR #{pr['number']} created on {created_date.strftime('%Y-%m-%d')}, week_start: {week_start.strftime('%Y-%m-%d')}")
                
                if week_key not in weekly_data:
                    weekly_data[week_key] = {
                        'week_start': week_start,
                        'week_label': week_start.strftime('%b %d'),
                        'total_prs': 0,
                        'merged_prs': 0
                    }
                
                weekly_data[week_key]['total_prs'] += 1
                if pr.get('merged_at'):
                    weekly_data[week_key]['merged_prs'] += 1
                    
            except Exception as e:
                logger.error(f"Error processing PR date: {e}")
                continue
        
        logger.info(f"Found {len(weekly_data)} weeks with PRs")
        for week_key, week_data in weekly_data.items():
            logger.info(f"Week {week_key}: {week_data['total_prs']} total, {week_data['merged_prs']} merged")
        
        # Sort by week and get last 4 weeks
        sorted_weeks = sorted(weekly_data.values(), key=lambda x: x['week_start'], reverse=True)
        last_4_weeks = sorted_weeks[:4]
        
        logger.info(f"Returning {len(last_4_weeks)} weeks for display")
        
        # Reverse to show oldest to newest
        return list(reversed(last_4_weeks))
    
    def _calculate_date_range(self, prs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate the date range of the PR data"""
        if not prs:
            return {
                'start_date': None,
                'end_date': None,
                'formatted_range': 'No data available for the selected period',
                'has_data': False
            }
        
        # Extract created_at dates and sort them
        dates = []
        for pr in prs:
            try:
                created_date = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))
                dates.append(created_date)
            except Exception as e:
                logger.warning(f"Error parsing date {pr.get('created_at', 'unknown')}: {e}")
                continue
        
        if not dates:
            return {
                'start_date': None,
                'end_date': None,
                'formatted_range': 'No valid date data available',
                'has_data': False
            }
        
        dates.sort()
        start_date = dates[0]
        end_date = dates[-1]
        
        # Format dates in human-readable format
        start_formatted = start_date.strftime('%b %d, %Y')
        end_formatted = end_date.strftime('%b %d, %Y')
        
        if start_date.date() == end_date.date():
            formatted_range = start_formatted
        else:
            formatted_range = f"{start_formatted} – {end_formatted}"
        
        return {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'formatted_range': formatted_range,
            'has_data': True,
            'total_days': (end_date - start_date).days + 1
        }
    
    def _format_filter_description(self, start_date: str, end_date: str) -> str:
        """Format filter description for UI display"""
        if not start_date and not end_date:
            return "All available data"
        
        try:
            if start_date and end_date:
                start_dt = datetime.fromisoformat(start_date)
                end_dt = datetime.fromisoformat(end_date)
                
                # Check if it's a single month
                if start_dt.year == end_dt.year and start_dt.month == end_dt.month:
                    return f"{start_dt.strftime('%B %Y')} ({start_date} → {end_date})"
                else:
                    return f"{start_dt.strftime('%b %d, %Y')} → {end_dt.strftime('%b %d, %Y')}"
            
            elif start_date:
                start_dt = datetime.fromisoformat(start_date)
                return f"From {start_dt.strftime('%b %d, %Y')}"
            
            elif end_date:
                end_dt = datetime.fromisoformat(end_date)
                return f"Until {end_dt.strftime('%b %d, %Y')}"
                
        except Exception as e:
            logger.error(f"Error formatting filter description: {e}")
            return f"Date range: {start_date or 'N/A'} to {end_date or 'N/A'}"
    
    def _calculate_pr_leaderboard(self, prs: List[Dict[str, Any]], repo_name: str) -> List[Dict[str, Any]]:
        """Calculate PR contributor leaderboard for a repository"""
        if not prs:
            return []
        
        logger.info(f"Calculating PR leaderboard for {repo_name} with {len(prs)} PRs")
        
        # Get detailed PR data with additions/deletions
        detailed_pr_data = self._get_detailed_pr_data(prs, repo_name)
        
        # Group by user
        user_stats = {}
        
        for pr in detailed_pr_data:
            user = pr['user']['login']
            additions = pr.get('additions', 0)
            deletions = pr.get('deletions', 0)
            total_changes = additions + deletions
            
            if user not in user_stats:
                user_stats[user] = {
                    'username': user,
                    'total_prs': 0,
                    'total_lines_changed': 0,
                    'total_additions': 0,
                    'total_deletions': 0,
                    'pr_sizes': []
                }
            
            user_stats[user]['total_prs'] += 1
            user_stats[user]['total_lines_changed'] += total_changes
            user_stats[user]['total_additions'] += additions
            user_stats[user]['total_deletions'] += deletions
            user_stats[user]['pr_sizes'].append(total_changes)
        
        # Calculate averages and format for leaderboard
        leaderboard = []
        for user, stats in user_stats.items():
            avg_pr_size = sum(stats['pr_sizes']) / len(stats['pr_sizes']) if stats['pr_sizes'] else 0
            
            leaderboard.append({
                'username': user,
                'total_prs': stats['total_prs'],
                'avg_pr_size': round(avg_pr_size, 1),
                'total_lines_changed': stats['total_lines_changed'],
                'total_additions': stats['total_additions'],
                'total_deletions': stats['total_deletions'],
                'repository': repo_name
            })
        
        # Sort by total PRs (descending) and get top 5
        leaderboard.sort(key=lambda x: x['total_prs'], reverse=True)
        top_5 = leaderboard[:5]
        
        logger.info(f"PR leaderboard for {repo_name}: {len(top_5)} contributors")
        
        return top_5
    
    def _calculate_team_leaderboard(self, metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Calculate team-level leaderboard aggregating contributors across all repositories"""
        if not metrics:
            return []
        
        repositories_count = len([m for m in metrics if m.get('leaderboard')])
        logger.info(f"Calculating team-level leaderboard for {repositories_count} repositories")
        
        # Aggregate user stats across all repositories
        team_user_stats = {}
        
        for metric in metrics:
            if not metric.get('leaderboard'):
                continue
                
            repo_name = metric['repository']
            for contributor in metric['leaderboard']:
                username = contributor['username']
                
                if username not in team_user_stats:
                    team_user_stats[username] = {
                        'username': username,
                        'total_prs': 0,
                        'total_lines_changed': 0,
                        'total_additions': 0,
                        'total_deletions': 0,
                        'repositories': set(),
                        'pr_sizes': []
                    }
                
                # Aggregate stats
                team_user_stats[username]['total_prs'] += contributor['total_prs']
                team_user_stats[username]['total_lines_changed'] += contributor['total_lines_changed']
                team_user_stats[username]['total_additions'] += contributor['total_additions']
                team_user_stats[username]['total_deletions'] += contributor['total_deletions']
                team_user_stats[username]['repositories'].add(repo_name)
                team_user_stats[username]['pr_sizes'].extend([contributor['avg_pr_size']] * contributor['total_prs'])
        
        # Format for team leaderboard
        team_leaderboard = []
        for username, stats in team_user_stats.items():
            avg_pr_size = int(mean(stats['pr_sizes'])) if stats['pr_sizes'] else 0
            repositories_list = sorted(list(stats['repositories']))
            
            team_leaderboard.append({
                'username': username,
                'total_prs': stats['total_prs'],
                'total_lines_changed': stats['total_lines_changed'],
                'total_additions': stats['total_additions'],
                'total_deletions': stats['total_deletions'],
                'avg_pr_size': avg_pr_size,
                'repositories_count': len(repositories_list),
                'repositories': repositories_list
            })
        
        # Sort by total PR count (descending) and take top 5
        team_leaderboard.sort(key=lambda x: x['total_prs'], reverse=True)
        top_contributors = team_leaderboard[:5]
        
        logger.info(f"Team leaderboard: {len(top_contributors)} contributors (from {len(team_user_stats)} total)")
        for contributor in top_contributors:
            logger.info(f"  {contributor['username']}: {contributor['total_prs']} PRs, {contributor['total_lines_changed']} lines, {contributor['repositories_count']} repos")
        
        return top_contributors
    
    def _get_detailed_pr_data(self, prs: List[Dict[str, Any]], repo_name: str) -> List[Dict[str, Any]]:
        """Get detailed PR data including additions/deletions"""
        cache_key = f"detailed_prs_{repo_name}"
        
        # Check cache first
        cached_detailed_prs = self.cache.get(cache_key)
        if cached_detailed_prs is not None:
            logger.info(f"Using cached detailed PR data for repository: {repo_name}")
            return cached_detailed_prs
        
        # Return dummy data if in demo mode
        if config.DEMO_MODE:
            logger.info(f"🎭 DEMO MODE: Returning dummy detailed PR data for {len(prs)} PRs in {repo_name}")
            # Since we're in demo mode, the PRs already have detailed data from dummy_data
            detailed_prs = prs.copy()
            # Cache dummy data
            self.cache.set(cache_key, detailed_prs)
            return detailed_prs
        
        logger.info(f"Fetching detailed PR data for {len(prs)} PRs in {repo_name}")
        detailed_prs = []
        
        # Batch fetch detailed data for each PR
        for pr in prs:
            try:
                pr_number = pr['number']
                url = f"https://api.github.com/repos/{self.organization}/{repo_name}/pulls/{pr_number}"
                
                # Add rate limiting delay
                time.sleep(REQUEST_DELAY)
                
                response = requests.get(url, headers=self.headers)
                if response.status_code == 200:
                    detailed_pr = response.json()
                    detailed_prs.append(detailed_pr)
                else:
                    logger.warning(f"Failed to fetch detailed data for PR #{pr_number}: {response.status_code}")
                    # Use original PR data as fallback (without additions/deletions)
                    fallback_pr = pr.copy()
                    fallback_pr['additions'] = 0
                    fallback_pr['deletions'] = 0
                    detailed_prs.append(fallback_pr)
                    
            except Exception as e:
                logger.error(f"Error fetching detailed PR data for PR #{pr.get('number', 'unknown')}: {e}")
                continue
        
        # Cache the result for 12 hours
        self.cache.set(cache_key, detailed_prs)
        logger.info(f"Cached detailed PR data for {len(detailed_prs)} PRs in {repo_name}")
        
        return detailed_prs
    
    def _calculate_first_commit_to_merge(self, prs: List[Dict[str, Any]], repo_name: str) -> float:
        """Calculate first commit to merge time in hours"""
        if not prs:
            return 0
        
        # Get all merged PRs
        merged_prs = [pr for pr in prs if pr.get('merged_at')]
        if not merged_prs:
            return 0
        
        # Extract PR numbers and create PR data lookup
        pr_numbers = [pr['number'] for pr in merged_prs]
        pr_data = {pr['number']: pr for pr in merged_prs}
        
        # Fetch all commits for all PRs (with caching)
        all_commits = self._get_all_pr_commits(repo_name, pr_numbers, pr_data)
        
        commit_to_merge_times = []
        
        for pr in merged_prs:
            try:
                # Get commits for this PR from batch data
                commits = all_commits.get(pr['number'], [])
                if not commits:
                    continue
                
                first_commit_date = datetime.fromisoformat(commits[0]['commit']['author']['date'].replace('Z', '+00:00'))
                merged_at = datetime.fromisoformat(pr['merged_at'].replace('Z', '+00:00'))
                
                commit_to_merge_hours = (merged_at - first_commit_date).total_seconds() / 3600
                commit_to_merge_times.append(commit_to_merge_hours)
                
            except Exception as e:
                logger.error(f"Error calculating commit to merge time for PR #{pr['number']}: {e}")
                continue
        
        return mean(commit_to_merge_times) if commit_to_merge_times else 0
    
    def _get_all_pr_reviews(self, repo_name: str, pr_numbers: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        """Get reviews for all PRs in a repository"""
        cache_key = f"all_reviews_{repo_name}"
        
        # Check cache first
        cached_reviews = self.cache.get(cache_key)
        if cached_reviews is not None:
            logger.info(f"Using cached reviews for repository: {repo_name}")
            return cached_reviews
        
        # Return dummy data if in demo mode
        if config.DEMO_MODE:
            logger.info(f"🎭 DEMO MODE: Returning dummy reviews for {len(pr_numbers)} PRs in {repo_name}")
            all_reviews = {}
            for pr_number in pr_numbers:
                all_reviews[pr_number] = dummy_data.get_dummy_pr_reviews(pr_number)
            # Cache dummy data
            self.cache.set(cache_key, all_reviews)
            return all_reviews
        
        logger.info(f"Fetching reviews for {len(pr_numbers)} PRs in {repo_name}")
        all_reviews = {}
        
        for pr_number in pr_numbers:
            url = f"https://api.github.com/repos/{self.organization}/{repo_name}/pulls/{pr_number}/reviews"
            
            # Add rate limiting delay
            time.sleep(REQUEST_DELAY)
            
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                all_reviews[pr_number] = []
                continue
            
            reviews = response.json()
            # Sort by submitted_at to get the first review
            sorted_reviews = sorted(reviews, key=lambda x: x['submitted_at']) if reviews else []
            all_reviews[pr_number] = sorted_reviews
        
        # Cache the result
        self.cache.set(cache_key, all_reviews)
        logger.info(f"Cached reviews for {len(pr_numbers)} PRs in {repo_name}")
        
        return all_reviews
    
    def _get_pr_reviews(self, pr_number: int, repo_name: str) -> List[Dict[str, Any]]:
        """Get reviews for a specific PR (legacy method for compatibility)"""
        # This method now just returns from the batch-cached data
        cache_key = f"all_reviews_{repo_name}"
        cached_reviews = self.cache.get(cache_key)
        
        if cached_reviews is not None and pr_number in cached_reviews:
            return cached_reviews[pr_number]
        
        # Fallback to individual fetch if not in batch cache
        url = f"https://api.github.com/repos/{self.organization}/{repo_name}/pulls/{pr_number}/reviews"
        
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            return []
        
        reviews = response.json()
        return sorted(reviews, key=lambda x: x['submitted_at']) if reviews else []
    
    def _get_all_pr_commits(self, repo_name: str, pr_numbers: List[int], pr_data: Dict[int, Dict[str, Any]] = None) -> Dict[int, List[Dict[str, Any]]]:
        """Get commits for all PRs in a repository"""
        cache_key = f"all_commits_{repo_name}"
        
        # Check cache first
        cached_commits = self.cache.get(cache_key)
        if cached_commits is not None:
            logger.info(f"Using cached commits for repository: {repo_name}")
            return cached_commits
        
        # Return dummy data if in demo mode
        if config.DEMO_MODE:
            logger.info(f"🎭 DEMO MODE: Returning dummy commits for {len(pr_numbers)} PRs in {repo_name}")
            all_commits = {}
            for pr_number in pr_numbers:
                # Get PR dates if available for more realistic commit timing
                pr_info = pr_data.get(pr_number, {}) if pr_data else {}
                pr_created_at = pr_info.get('created_at')
                pr_merged_at = pr_info.get('merged_at')
                all_commits[pr_number] = dummy_data.get_dummy_pr_commits(pr_number, pr_created_at, pr_merged_at)
            # Cache dummy data
            self.cache.set(cache_key, all_commits)
            return all_commits
        
        logger.info(f"Fetching commits for {len(pr_numbers)} PRs in {repo_name}")
        all_commits = {}
        
        for pr_number in pr_numbers:
            url = f"https://api.github.com/repos/{self.organization}/{repo_name}/pulls/{pr_number}/commits"
            
            # Add rate limiting delay
            time.sleep(REQUEST_DELAY)
            
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                all_commits[pr_number] = []
                continue
            
            commits = response.json()
            # Sort by commit date to get the first commit
            sorted_commits = sorted(commits, key=lambda x: x['commit']['author']['date']) if commits else []
            all_commits[pr_number] = sorted_commits
        
        # Cache the result
        self.cache.set(cache_key, all_commits)
        logger.info(f"Cached commits for {len(pr_numbers)} PRs in {repo_name}")
        
        return all_commits
    
    def _get_pr_commits(self, pr_number: int, repo_name: str) -> List[Dict[str, Any]]:
        """Get commits for a specific PR (legacy method for compatibility)"""
        # This method now just returns from the batch-cached data
        cache_key = f"all_commits_{repo_name}"
        cached_commits = self.cache.get(cache_key)
        
        if cached_commits is not None and pr_number in cached_commits:
            return cached_commits[pr_number]
        
        # Fallback to individual fetch if not in batch cache
        url = f"https://api.github.com/repos/{self.organization}/{repo_name}/pulls/{pr_number}/commits"
        
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            return []
        
        commits = response.json()
        return sorted(commits, key=lambda x: x['commit']['author']['date']) if commits else []
    
    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        logger.info("GitHub API cache cleared")
    
    def clear_repo_cache(self, repo_name: str):
        """Clear cache for specific repository"""
        cache_keys_to_clear = []
        for key in self.cache.cache.keys():
            if repo_name in key:
                cache_keys_to_clear.append(key)
        
        for key in cache_keys_to_clear:
            if key in self.cache.cache:
                del self.cache.cache[key]
        
        logger.info(f"Cleared cache for repository: {repo_name} ({len(cache_keys_to_clear)} items)")
    
    def clear_team_cache(self, team_name: str) -> int:
        """Clear cache for specific team"""
        return self.cache.clear_team_cache(team_name)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        cache_breakdown = {
            'repo_metrics': 0,
            'team_default': 0,
            'team_month': 0,
            'prs': 0,
            'all_reviews': 0,
            'all_commits': 0,
            'detailed_prs': 0,
            'rate_limit': 0,
            'other': 0
        }
        
        for key in self.cache.cache.keys():
            if key.startswith('repo_metrics_'):
                cache_breakdown['repo_metrics'] += 1
            elif key.endswith('_last30PR'):
                cache_breakdown['team_default'] += 1
            elif '_month_' in key:
                cache_breakdown['team_month'] += 1
            elif key.startswith('prs_'):
                cache_breakdown['prs'] += 1
            elif key.startswith('all_reviews_'):
                cache_breakdown['all_reviews'] += 1
            elif key.startswith('all_commits_'):
                cache_breakdown['all_commits'] += 1
            elif key.startswith('detailed_prs_'):
                cache_breakdown['detailed_prs'] += 1
            elif key == 'rate_limit':
                cache_breakdown['rate_limit'] += 1
            else:
                cache_breakdown['other'] += 1
        
        return {
            'size': self.cache.size(),
            'ttl_seconds': self.cache.default_ttl,
            'breakdown': cache_breakdown
        }

    def get_global_user_metrics(self, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Get global user metrics aggregated across all teams with monthly breakdown"""
        logger.info(f"Getting global user metrics (date range: {start_date} to {end_date})")
        
        all_teams = self.get_all_team_names()
        global_user_stats = {}
        monthly_user_stats = {}
        
        total_processed_prs = 0
        total_processed_teams = 0
        
        for team_name in all_teams:
            try:
                team_metrics = self.get_all_team_metrics(team_name, start_date=start_date, end_date=end_date)
                total_processed_teams += 1
                
                logger.info(f"Processing team: {team_name} with {len(team_metrics.get('metrics', []))} repositories")
                
                # Process each repository in the team
                for repo_metric in team_metrics.get('metrics', []):
                    repo_name = repo_metric.get('repository', 'unknown')
                    pr_data_list = repo_metric.get('pr_data', [])
                    
                    logger.info(f"Processing repository: {repo_name} with {len(pr_data_list)} PRs")
                    
                    # Process each PR for user statistics
                    for pr_data in pr_data_list:
                        total_processed_prs += 1
                        
                        # Check if PR is merged
                        if not pr_data.get('merged_at'):
                            continue
                        
                        # Extract username - try different possible structures
                        username = None
                        if 'author' in pr_data:
                            username = pr_data['author']
                        elif 'user' in pr_data and isinstance(pr_data['user'], dict):
                            username = pr_data['user'].get('login')
                        elif 'user' in pr_data and isinstance(pr_data['user'], str):
                            username = pr_data['user']
                        
                        if not username or username == 'unknown':
                            logger.debug(f"Skipping PR due to missing username: {pr_data.get('pr_number', 'unknown')}")
                            continue
                        
                        # Get PR month
                        try:
                            created_at_str = pr_data.get('created_at', '')
                            if not created_at_str:
                                continue
                                
                            created_date = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                            month_key = created_date.strftime('%Y-%m')
                            month_label = created_date.strftime('%b %Y')
                        except Exception as e:
                            logger.debug(f"Error parsing date for PR {pr_data.get('pr_number', 'unknown')}: {e}")
                            continue
                        
                        # Calculate PR size - try different possible structures
                        pr_size = 0
                        if 'additions' in pr_data and 'deletions' in pr_data:
                            pr_size = pr_data.get('additions', 0) + pr_data.get('deletions', 0)
                        elif 'total_lines_changed' in pr_data:
                            pr_size = pr_data.get('total_lines_changed', 0)
                        
                        # Initialize global user stats
                        if username not in global_user_stats:
                            global_user_stats[username] = {
                                'username': username,
                                'total_prs': 0,
                                'total_lines_changed': 0,
                                'pr_sizes': [],
                                'teams': set(),
                                'repositories': set(),
                                'months': set()
                            }
                        
                        # Update global stats
                        global_user_stats[username]['total_prs'] += 1
                        global_user_stats[username]['total_lines_changed'] += pr_size
                        global_user_stats[username]['pr_sizes'].append(pr_size)
                        global_user_stats[username]['teams'].add(team_name)
                        global_user_stats[username]['repositories'].add(repo_name)
                        global_user_stats[username]['months'].add(month_key)
                        
                        # Initialize monthly stats
                        if month_key not in monthly_user_stats:
                            monthly_user_stats[month_key] = {
                                'month_key': month_key,
                                'month_label': month_label,
                                'users': {}
                            }
                        
                        if username not in monthly_user_stats[month_key]['users']:
                            monthly_user_stats[month_key]['users'][username] = {
                                'username': username,
                                'total_prs': 0,
                                'total_lines_changed': 0,
                                'pr_sizes': []
                            }
                        
                        # Update monthly stats
                        monthly_user_stats[month_key]['users'][username]['total_prs'] += 1
                        monthly_user_stats[month_key]['users'][username]['total_lines_changed'] += pr_size
                        monthly_user_stats[month_key]['users'][username]['pr_sizes'].append(pr_size)
                
                logger.info(f"Processed team: {team_name} - Found {len(global_user_stats)} unique users so far")
            except Exception as e:
                logger.error(f"Error processing team {team_name} for global user metrics: {e}")
                continue
        
        logger.info(f"Global user metrics summary: {total_processed_teams} teams, {total_processed_prs} PRs, {len(global_user_stats)} unique users")
        
        # Calculate averages and format data
        formatted_global_stats = []
        for username, stats in global_user_stats.items():
            avg_pr_size = mean(stats['pr_sizes']) if stats['pr_sizes'] else 0
            
            formatted_global_stats.append({
                'username': username,
                'total_prs': stats['total_prs'],
                'total_lines_changed': stats['total_lines_changed'],
                'avg_pr_size': round(avg_pr_size, 0),
                'teams_count': len(stats['teams']),
                'teams': sorted(list(stats['teams'])),
                'repositories_count': len(stats['repositories']),
                'repositories': sorted(list(stats['repositories'])),
                'months_active': len(stats['months'])
            })
        
        # Format monthly data
        formatted_monthly_stats = []
        for month_key in sorted(monthly_user_stats.keys(), reverse=True):
            month_data = monthly_user_stats[month_key]
            month_users = []
            
            for username, user_stats in month_data['users'].items():
                avg_pr_size = mean(user_stats['pr_sizes']) if user_stats['pr_sizes'] else 0
                
                month_users.append({
                    'username': username,
                    'total_prs': user_stats['total_prs'],
                    'total_lines_changed': user_stats['total_lines_changed'],
                    'avg_pr_size': round(avg_pr_size, 0)
                })
            
            # Sort users by PR count for the month
            month_users.sort(key=lambda x: x['total_prs'], reverse=True)
            
            formatted_monthly_stats.append({
                'month_key': month_key,
                'month_label': month_data['month_label'],
                'users': month_users,
                'total_prs_month': sum(user['total_prs'] for user in month_users),
                'top_3_users': month_users[:3]
            })
        
        # Sort global stats by total PRs
        formatted_global_stats.sort(key=lambda x: x['total_prs'], reverse=True)
        
        # Get top 5 global contributors
        top_5_global = formatted_global_stats[:5]
        
        # Prepare monthly chart data
        monthly_chart_data = self._prepare_monthly_chart_data(formatted_monthly_stats)
        
        logger.info(f"Final global user metrics: {len(formatted_global_stats)} users, {len(formatted_monthly_stats)} months")
        
        return {
            'global_users': formatted_global_stats,
            'monthly_stats': formatted_monthly_stats,
            'top_5_global': top_5_global,
            'monthly_chart_data': monthly_chart_data,
            'total_contributors': len(formatted_global_stats),
            'total_months': len(formatted_monthly_stats),
            'last_updated': datetime.now().isoformat()
        }
    
    def _prepare_monthly_chart_data(self, monthly_stats: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Prepare monthly chart data for top contributors"""
        if not monthly_stats:
            return {}
        
        # Get all unique users and sort by total PRs across all months
        all_users = {}
        for month_data in monthly_stats:
            for user in month_data['users']:
                username = user['username']
                if username not in all_users:
                    all_users[username] = 0
                all_users[username] += user['total_prs']
        
        # Get top 10 contributors globally
        top_users = sorted(all_users.items(), key=lambda x: x[1], reverse=True)[:10]
        top_usernames = [user[0] for user in top_users]
        
        # Prepare chart data
        months = [month['month_label'] for month in monthly_stats]
        
        # Colors for different users (Sapphire Blue gradient)
        base_colors = [
            'rgba(13, 71, 161, 0.8)',      # Sapphire Blue
            'rgba(25, 118, 210, 0.8)',     # Lighter Blue
            'rgba(33, 150, 243, 0.8)',     # Light Blue
            'rgba(66, 165, 245, 0.8)',     # Lighter Blue
            'rgba(100, 181, 246, 0.8)',    # Very Light Blue
            'rgba(144, 202, 249, 0.8)',    # Pale Blue
            'rgba(187, 222, 251, 0.8)',    # Very Pale Blue
            'rgba(227, 242, 253, 0.8)',    # Almost White Blue
            'rgba(13, 71, 161, 0.6)',      # Sapphire Blue (transparent)
            'rgba(25, 118, 210, 0.6)'      # Lighter Blue (transparent)
        ]
        
        datasets = []
        for i, username in enumerate(top_usernames):
            user_data = []
            for month_data in monthly_stats:
                user_prs = 0
                for user in month_data['users']:
                    if user['username'] == username:
                        user_prs = user['total_prs']
                        break
                user_data.append(user_prs)
            
            datasets.append({
                'label': username,
                'data': user_data,
                'backgroundColor': base_colors[i % len(base_colors)],
                'borderColor': base_colors[i % len(base_colors)].replace('0.8', '1').replace('0.6', '1'),
                'borderWidth': 1
            })
        
        return {
            'labels': months,
            'datasets': datasets
        }

# Global instance
github_service = GitHubService()

# Convenience functions for Flask routes
def load_config():
    """Load configuration from data/github_data.json"""
    return github_service.load_config()

def get_all_team_names():
    """Get all team names from configuration"""
    return github_service.get_all_team_names()

def get_team_repositories(team_name: str):
    """Get repositories for a specific team"""
    return github_service.get_team_repositories(team_name)

def get_repo_metrics(repo_name: str):
    """Calculate metrics for a specific repository"""
    return github_service.get_repo_metrics(repo_name)

def get_all_team_metrics(team_name: str, start_date: str = None, end_date: str = None):
    """Get metrics for all repositories in a team with optional date filtering"""
    return github_service.get_all_team_metrics(team_name, start_date=start_date, end_date=end_date)

def get_all_teams_metrics(start_date: str = None, end_date: str = None):
    """Get metrics for all teams with optional date filtering"""
    return github_service.get_all_teams_metrics(start_date=start_date, end_date=end_date)

def clear_team_cache(team_name: str) -> int:
    """Clear cache for specific team"""
    return github_service.clear_team_cache(team_name)

def get_global_user_metrics(start_date: str = None, end_date: str = None):
    """Get global user metrics aggregated across all teams with monthly breakdown"""
    return github_service.get_global_user_metrics(start_date=start_date, end_date=end_date)

def is_demo_mode() -> bool:
    """Check if demo mode is active"""
    return config.DEMO_MODE
