from flask import Flask, render_template, jsonify, redirect, url_for
import json
from github_service import get_all_team_metrics, get_all_team_names, load_config, clear_team_cache, github_service, get_all_teams_metrics, get_global_user_metrics
from typing import List, Dict, Any

app = Flask(__name__, static_url_path='/static', static_folder='static')

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/documentation')
def documentation():
    """Documentation page"""
    return render_template('documentation.html')

@app.route('/github')
def github_redirect():
    """Redirect to team selection page"""
    return redirect(url_for('github_team_selection'))

@app.route('/github-metrics')
def github_team_selection():
    """GitHub team selection page"""
    try:
        team_names = get_all_team_names()
        return render_template('github_team_selection.html', team_names=team_names)
    except Exception as e:
        return render_template('github_team_selection.html', team_names=[], error=str(e))

@app.route('/github-metrics/<team_name>')
def github_metrics(team_name):
    """GitHub metrics page for specific team with optional date filtering"""
    from flask import request
    
    try:
        # Validate team name exists
        team_names = get_all_team_names()
        if team_name not in team_names:
            return render_template('github_metrics.html', 
                                 metrics=[], 
                                 overall_date_range={
                                     'start_date': None,
                                     'end_date': None,
                                     'formatted_range': 'Team not found',
                                     'has_data': False
                                 },
                                 chart_data={},
                                 chart_data_json=json.dumps({}),
                                 team_name=team_name,
                                 error=f'Team "{team_name}" not found')
        
        # Get optional date range parameters from URL
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Backend prioritization: If both custom and month filters are provided, prioritize custom
        # (This shouldn't happen with proper frontend mutual exclusivity, but serves as a failsafe)
        if start_date and end_date:
            # Custom date range takes priority
            pass
        else:
            # No valid custom range, clear any partial dates
            start_date = None
            end_date = None
        
        # Get all metrics for the team with date filtering
        team_data = get_all_team_metrics(team_name, start_date=start_date, end_date=end_date)
        metrics = team_data['metrics']
        top_5_mr_times = team_data['top_5_mr_times']
        team_leaderboard = team_data.get('team_leaderboard', [])
        overall_date_range = team_data['overall_date_range']
        
        # Prepare data for charts
        chart_data = prepare_chart_data(metrics)
        
        return render_template('github_metrics.html', 
                             metrics=metrics, 
                             top_5_mr_times=top_5_mr_times,
                             team_leaderboard=team_leaderboard,
                             overall_date_range=overall_date_range,
                             chart_data=chart_data,
                             chart_data_json=json.dumps(chart_data),
                             team_name=team_name)
    except Exception as e:
        return render_template('github_metrics.html', 
                             metrics=[], 
                             overall_date_range={
                                 'start_date': None,
                                 'end_date': None,
                                 'formatted_range': 'No data available due to error',
                                 'has_data': False
                             },
                             chart_data={},
                             chart_data_json=json.dumps({}),
                             team_name=team_name,
                             error=str(e))

@app.route('/api/github/metrics')
@app.route('/api/github/metrics/<team_name>')
def api_github_metrics(team_name=None):
    """API endpoint for GitHub metrics with optional date range filtering"""
    from flask import request
    from datetime import datetime
    
    try:
        if team_name is None:
            # Default to first team if no team specified
            team_names = get_all_team_names()
            if not team_names:
                return jsonify({
                    'success': False,
                    'error': 'No teams found in configuration'
                }), 404
            team_name = team_names[0]
        else:
            # Validate team name exists
            team_names = get_all_team_names()
            if team_name not in team_names:
                return jsonify({
                    'success': False,
                    'error': f'Team "{team_name}" not found'
                }), 404
        
        # Get optional date range parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Validate date format if provided
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid start_date format. Use YYYY-MM-DD'
                }), 400
        
        if end_date:
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid end_date format. Use YYYY-MM-DD'
                }), 400
        
        # Backend prioritization: Ensure both start and end dates are provided for filtering
        if not (start_date and end_date):
            start_date = None
            end_date = None
        
        team_data = get_all_team_metrics(team_name, start_date=start_date, end_date=end_date)
        
        return jsonify({
            'success': True,
            'team_name': team_name,
            'start_date': start_date,
            'end_date': end_date,
            'metrics': team_data['metrics'],
            'top_5_mr_times': team_data['top_5_mr_times'],
            'team_leaderboard': team_data.get('team_leaderboard', []),
            'overall_date_range': team_data['overall_date_range']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



@app.route('/api/clear-cache', methods=['POST'])
@app.route('/api/clear-cache/<team_name>', methods=['POST'])
def api_clear_cache(team_name=None):
    """API endpoint to clear cache - optionally for a specific team"""
    try:
        if team_name:
            # Clear cache for specific team only
            team_names = get_all_team_names()
            if team_name not in team_names:
                return jsonify({
                    'success': False,
                    'error': f'Team "{team_name}" not found'
                }), 404
            
            clear_result = clear_team_cache(team_name)
            return jsonify({
                'success': True,
                'message': f'Cache cleared for team "{team_name}"',
                'details': f'Cleared {clear_result} cache entries'
            })
        else:
            # Clear all cache (existing behavior)
            github_service.clear_cache()
            return jsonify({
                'success': True,
                'message': 'All cache cleared successfully'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/cache-stats')
def api_cache_stats():
    """API endpoint to get cache statistics"""
    try:
        cache_stats = github_service.get_cache_stats()
        return jsonify({
            'success': True,
            'cache_stats': cache_stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/team-comparison')
def team_comparison():
    """Team comparison dashboard page"""
    try:
        # Get metrics for all teams
        teams_data = get_all_teams_metrics()
        
        # Get global user metrics
        global_user_data = get_global_user_metrics()
        
        # Prepare data for charts
        chart_data = prepare_team_comparison_chart_data(teams_data['teams'])
        
        return render_template('team_comparison.html', 
                             teams_data=teams_data,
                             global_user_data=global_user_data,
                             chart_data=chart_data,
                             chart_data_json=json.dumps(chart_data),
                             global_user_chart_data_json=json.dumps(global_user_data.get('monthly_chart_data', {})))
    except Exception as e:
        return render_template('team_comparison.html', 
                             teams_data={'teams': [], 'total_teams': 0, 'last_updated': None},
                             global_user_data={'global_users': [], 'monthly_stats': [], 'top_5_global': [], 'monthly_chart_data': {}, 'total_contributors': 0, 'total_months': 0, 'last_updated': None},
                             chart_data={},
                             chart_data_json=json.dumps({}),
                             global_user_chart_data_json=json.dumps({}),
                             error=str(e))

@app.route('/api/team-comparison')
def api_team_comparison():
    """API endpoint for team comparison data"""
    try:
        teams_data = get_all_teams_metrics()
        return jsonify({
            'success': True,
            'data': teams_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/refresh-all-teams', methods=['POST'])
def api_refresh_all_teams():
    """API endpoint to refresh all teams data (clear cache and recalculate)"""
    try:
        team_names = get_all_team_names()
        
        # Clear cache for all teams
        total_cleared = 0
        for team_name in team_names:
            cleared_count = clear_team_cache(team_name)
            total_cleared += cleared_count
        
        # Also clear general cache
        github_service.clear_cache()
        
        return jsonify({
            'success': True,
            'message': f'Cache cleared for all {len(team_names)} teams',
            'details': f'Cleared {total_cleared} cache entries'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def prepare_chart_data(metrics):
    """Prepare data for Chart.js visualization"""
    if not metrics:
        return {}
    
    repositories = [metric['repository'] for metric in metrics]
    pr_throughput = [metric['pr_throughput'] for metric in metrics]
    mr_time = [metric['mr_time'] for metric in metrics]
    first_commit_to_merge = [metric['first_commit_to_merge'] for metric in metrics]
    
    # Prepare weekly data for charts
    weekly_data = prepare_weekly_chart_data(metrics)
    
    # Prepare leaderboard data for charts
    leaderboard_data = prepare_leaderboard_chart_data(metrics)
    
    return {
        'labels': repositories,
        'datasets': {
            'pr_throughput': {
                'label': 'PR Throughput (PRs/day)',
                'data': pr_throughput,
                'backgroundColor': 'rgba(13, 71, 161, 0.3)',
                'borderColor': 'rgba(13, 71, 161, 1)',
                'borderWidth': 1
            },
            'mr_time': {
                'label': 'MR Time (hours)',
                'data': mr_time,
                'backgroundColor': 'rgba(25, 118, 210, 0.3)',
                'borderColor': 'rgba(25, 118, 210, 1)',
                'borderWidth': 1
            },
            'first_commit_to_merge': {
                'label': 'First Commit to Merge (hours)',
                'data': first_commit_to_merge,
                'backgroundColor': 'rgba(33, 150, 243, 0.3)',
                'borderColor': 'rgba(33, 150, 243, 1)',
                'borderWidth': 1
            }
        },
        'weekly_data': weekly_data,
        'leaderboard_data': leaderboard_data
    }

def prepare_weekly_chart_data(metrics):
    """Prepare weekly data for charts"""
    if not metrics or not any(metric.get('weekly_counts') for metric in metrics):
        return {}
    
    # Get week labels from first metric that has data
    week_labels = []
    for metric in metrics:
        if metric.get('weekly_counts'):
            week_labels = [week['week_label'] for week in metric['weekly_counts']]
            break
    
    if not week_labels:
        return {}
    
    # Prepare data for each repository
    datasets = []
    colors = [
        'rgba(13, 71, 161, 0.8)',    # Sapphire Blue
        'rgba(25, 118, 210, 0.8)',   # Sapphire Secondary
        'rgba(33, 150, 243, 0.8)',   # Sapphire Light
        'rgba(255, 193, 7, 0.8)',    # Amber
        'rgba(144, 164, 174, 0.8)'   # Blue Gray
    ]
    
    for i, metric in enumerate(metrics):
        if metric.get('weekly_counts'):
            weekly_counts = [week['total_prs'] for week in metric['weekly_counts']]
        else:
            weekly_counts = [0] * len(week_labels)
        
        datasets.append({
            'label': metric['repository'],
            'data': weekly_counts,
            'backgroundColor': colors[i % len(colors)],
            'borderColor': colors[i % len(colors)].replace('0.8', '1'),
            'borderWidth': 1
        })
    
    return {
        'labels': week_labels,
        'datasets': datasets
    }

def prepare_leaderboard_chart_data(metrics):
    """Prepare leaderboard data for charts"""
    if not metrics:
        return {}
    
    # Collect all contributors across all repositories
    all_contributors = []
    
    for metric in metrics:
        if metric.get('leaderboard'):
            for contributor in metric['leaderboard']:
                all_contributors.append(contributor)
    
    if not all_contributors:
        return {}
    
    # Sort by total PRs and get top 10 contributors across all repos
    all_contributors.sort(key=lambda x: x['total_prs'], reverse=True)
    top_contributors = all_contributors[:10]
    
    # Prepare data for contributors chart
    contributor_labels = [f"{contrib['username']} ({contrib['repository']})" for contrib in top_contributors]
    contributor_prs = [contrib['total_prs'] for contrib in top_contributors]
    
    # Generate colors with gradient based on PR size
    max_pr_size = max([contrib['avg_pr_size'] for contrib in top_contributors]) if top_contributors else 1
    contributor_colors = []
    
    for contrib in top_contributors:
        # Create color gradient based on avg PR size (larger PR = darker color)
        intensity = min(contrib['avg_pr_size'] / max_pr_size, 1.0) if max_pr_size > 0 else 0.5
        # Use sapphire blue gradient - darker for larger PRs
        color = f'rgba(13, 71, 161, {0.3 + intensity * 0.7})'
        contributor_colors.append(color)
    
    # Prepare data for PR size chart
    pr_size_data = [contrib['avg_pr_size'] for contrib in top_contributors]
    
    return {
        'contributors': {
            'labels': contributor_labels,
            'data': contributor_prs,
            'backgroundColor': contributor_colors,
            'borderColor': 'rgba(106, 27, 154, 1)',
            'borderWidth': 1
        },
        'pr_sizes': {
            'labels': contributor_labels,
            'data': pr_size_data,
            'backgroundColor': 'rgba(255, 193, 7, 0.6)',
            'borderColor': 'rgba(255, 193, 7, 1)',
            'borderWidth': 1
        }
    }

def prepare_team_comparison_chart_data(teams: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Prepare data for team comparison charts"""
    if not teams:
        return {}
    
    team_names = [team['team_name'] for team in teams]
    pr_throughput = [team['pr_throughput'] for team in teams]
    avg_merge_time = [team['avg_merge_time'] for team in teams]
    avg_pr_size = [team['avg_pr_size'] for team in teams]
    total_merged_prs = [team['total_merged_prs'] for team in teams]
    
    # Sapphire Blue color scheme
    colors = [
        'rgba(13, 71, 161, 0.8)',    # Sapphire Blue
        'rgba(25, 118, 210, 0.8)',   # Sapphire Secondary
        'rgba(25, 118, 210, 0.8)',   # Sapphire Light
        'rgba(255, 193, 7, 0.8)',    # Amber
        'rgba(144, 164, 174, 0.8)',  # Blue Gray
        'rgba(33, 150, 243, 0.8)'    # Light Blue
    ]
    
    return {
        'labels': team_names,
        'datasets': {
            'pr_throughput': {
                'label': 'PR Throughput (PRs/day)',
                'data': pr_throughput,
                'backgroundColor': colors[:len(teams)],
                'borderColor': [color.replace('0.8', '1') for color in colors[:len(teams)]],
                'borderWidth': 1
            },
            'avg_merge_time': {
                'label': 'Average Merge Time (hours)',
                'data': avg_merge_time,
                'backgroundColor': colors[:len(teams)],
                'borderColor': [color.replace('0.8', '1') for color in colors[:len(teams)]],
                'borderWidth': 1
            },
            'avg_pr_size': {
                'label': 'Average PR Size (lines)',
                'data': avg_pr_size,
                'backgroundColor': colors[:len(teams)],
                'borderColor': [color.replace('0.8', '1') for color in colors[:len(teams)]],
                'borderWidth': 1
            },
            'total_merged_prs': {
                'label': 'Total Merged PRs',
                'data': total_merged_prs,
                'backgroundColor': colors[:len(teams)],
                'borderColor': [color.replace('0.8', '1') for color in colors[:len(teams)]],
                'borderWidth': 1
            }
        }
    }


if __name__ == '__main__':
    app.run(debug=True, port=5002)
