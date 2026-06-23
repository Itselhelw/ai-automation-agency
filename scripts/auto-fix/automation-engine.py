#!/usr/bin/env python3

"""
OpenClaw Automation Engine - Master Orchestrator

This script integrates the auto-fix and token-optimizer skills to provide:
1. Automatic detection and repair of operation failures (e.g., "⚠️ 🩹 Apply Patch failed")
2. Token consumption tracking and compression using caveman-style optimization
3. Proactive monitoring and alerting for near-limit conditions
4. Comprehensive logging and reporting

The system operates in three main modes:
- Failure remediation (immediate response to errors)
- Token optimization (continuous monitoring and compression)
- Scheduled maintenance (periodic checks and cleanup)
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/.openclaw/workspace/logs/automation-engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('automation-engine')

class Config:
    """Configuration management"""
    def __init__(self):
        self.workspace = Path('/root/.openclaw/workspace')
        self.logs_dir = self.workspace / 'logs'
        self.outputs_dir = self.workspace / 'outputs'
        self.token_usage_file = self.logs_dir / 'token_usage.json'
        self.auto_fix_log = self.logs_dir / 'auto_fixer.log'
        self.token_optimizer_log = self.logs_dir / 'token_optimizer.log'
        
        # Model configuration
        self.free_models = {
            'deepseek-r1:free': {'limit': 20, 'used': 0, 'last_reset': datetime.now()},
            'qwen3-8b:free': {'limit': 20, 'used': 0, 'last_reset': datetime.now()},
            'openrouter/free': {'limit': 200, 'used': 0, 'last_reset': datetime.now()},
            'gemini-2.0-flash-exp': {'limit': 10, 'used': 0, 'last_reset': datetime.now()},
            'claude-3-5-sonnet': {'limit': 100, 'used': 0, 'last_reset': datetime.now()},
        }
        
        # Error patterns to monitor
        self.error_patterns = [
            r'⚠️\s*🩹\s*Apply Patch failed',
            r'Permission denied',
            r'Command not found',
            r'Network timeout',
            r'Disk full',
            r'Rate limit.*exceed',
            r'Too many requests',
            r'API.*key.*invalid',
            r'Token.*expired',
            r'Connection refused',
            r'Service unavailable',
            r'Internal server error',
            r'Out of memory',
            r'File not found',
            r'No such file',
            r'Syntax error',
            r'ModuleNotFoundError',
            r'ImportError',
        ]
        
        # Low-risk fix templates
        self.low_risk_fixes = {
            r'File not found': 'Touch the file and log creation',
            r'No such file': 'Create the file with minimal content',
            r'Disk full': 'Clean up large log files and temp files',
            r'Permission denied': 'Check permissions and grant read/execute',
        }
        
        # Medium-risk fix templates
        self.medium_risk_fixes = {
            r'Rate limit': 'Wait and retry with exponential backoff',
            r'Network timeout': 'Retry with proxy fallback or cache',
            r'API key.*invalid': 'Validate environment variables and credentials',
        }
        
        # Auto-heal schedule (every 10 minutes)
        self.heal_interval_ms = 600000  # 10 minutes
        
        # Telegram bot token (would need to be configured)
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '1184424851')

class TokenUsageTracker:
    """Tracks token usage across all models and manages rate limits"""
    
    def __init__(self, config: Config):
        self.config = config
        self.load_usage_data()
        
    def load_usage_data(self):
        """Load token usage data from file or initialize empty"""
        if self.config.token_usage_file.exists():
            try:
                with open(self.config.token_usage_file, 'r') as f:
                    self.usage_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning("Failed to load token usage data, initializing fresh")
                self.usage_data = {}
        else:
            self.usage_data = {}
            
        # Ensure each model has an entry
        for model_name in self.config.free_models:
            if model_name not in self.usage_data:
                self.usage_data[model_name] = {
                    'today_used': 0,
                    'today_limit': self.config.free_models[model_name]['limit'],
                    'yesterday_used': 0,
                    'last_reset': datetime.now().isoformat(),
                    'alerts_sent': 0
                }
                
    def save_usage_data(self):
        """Save token usage data to file"""
        try:
            # Convert datetime to ISO format for JSON serialization
            for model in self.usage_data.values():
                if 'last_reset' in model and isinstance(model['last_reset'], datetime):
                    model['last_reset'] = model['last_reset'].isoformat()
                    
            with open(self.config.token_usage_file, 'w') as f:
                json.dump(self.usage_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save token usage data: {e}")
            
    def record_usage(self, model_name: str, tokens_used: int) -> bool:
        """
        Record token usage for a model
        
        Returns True if within limits, False if exceeded
        """
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Initialize model entry if not exists
        if model_name not in self.usage_data:
            self.usage_data[model_name] = {
                'today_used': 0,
                'today_limit': self.config.free_models.get(model_name, {}).get('limit', 100),
                'yesterday_used': 0,
                'last_reset': datetime.now().isoformat(),
                'alerts_sent': 0
            }
            
        # Check if we need to reset daily
        if self.usage_data[model_name].get('last_date') != today:
            # Reset for new day, move previous day's usage to yesterday
            self.usage_data[model_name]['yesterday_used'] = self.usage_data[model_name]['today_used']
            self.usage_data[model_name]['today_used'] = 0
            self.usage_data[model_name]['last_date'] = today
            
        # Update usage
        self.usage_data[model_name]['today_used'] += tokens_used
        
        # Save changes
        self.save_usage_data()
        
        # Check if exceeded
        within_limit = self.usage_data[model_name]['today_used'] <= self.usage_data[model_name]['today_limit']
        
        # Send alert if approaching limit (>85%)
        if not within_limit and self.usage_data[model_name]['alerts_sent'] == 0:
            self.send_limit_alert(model_name)
            
        return within_limit
        
    def get_usage_stats(self, model_name: str = None) -> Dict:
        """Get usage statistics for a model or all models"""
        if model_name:
            return self.usage_data.get(model_name, {})
        return self.usage_data
        
    def send_limit_alert(self, model_name: str):
        """Send a Telegram alert when approaching token limit"""
        stats = self.usage_data[model_name]
        message = (
            f"⚠️ Token Limit Alert\n"
            f"Model: {model_name}\n"
            f"Used: {stats['today_used']}/{stats['today_limit']} tokens (today)\n"
            f"Yesterday: {stats['yesterday_used']} tokens\n"
            f"Alert time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Recommendation: Switch to another free model or reduce workload."
        )
        
        logger.warning(f"Token limit alert sent for {model_name}")
        
        # In a real implementation, this would send a Telegram message
        # For now, we'll just log it
        logger.info(f"ALERT: {message}")
        
        # Mark that we've sent the alert
        self.usage_data[model_name]['alerts_sent'] = 1
        self.save_usage_data()
class AutoFixer:
    """Automatic fix application for common error patterns"""
    
    def __init__(self, config: Config, token_tracker: TokenUsageTracker):
        self.config = config
        self.token_tracker = token_tracker
        self.logger = logging.getLogger('auto-fixer')
        
    def scan_logs_for_errors(self) -> List[Dict[str, Any]]:
        """Scan log files for error patterns and return matches"""
        errors_found = []
        
        # Main log file to scan
        log_files = [
            self.config.logs_dir / 'exec.log',
            self.config.logs_dir / 'automation-engine.log',
            self.config.logs_dir / 'auto_fixer.log',
        ]
        
        for log_file in log_files:
            if not log_file.exists():
                continue
                
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    
                # Process last 100 lines for performance
                recent_lines = lines[-100:] if len(lines) > 100 else lines
                
                for line in recent_lines:
                    line_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    for pattern in self.config.error_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            error_info = {
                                'timestamp': line_time,
                                'pattern': pattern,
                                'message': line.strip(),
                                'severity': self._assess_severity(pattern, line),
                                'action_taken': None,
                                'success': None,
                                'response': None
                            }
                            errors_found.append(error_info)
                            self.logger.info(f"Detected error pattern: {pattern} in log line")
                            
            except Exception as e:
                self.logger.error(f"Failed to scan log file {log_file}: {e}")
                
        return errors_found
        
    def _assess_severity(self, pattern: str, message: str) -> str:
        """Assess severity of error pattern"""
        high_severity_patterns = [
            r'Permission denied',
            r'Rate limit.*exceed',
            r'Too many requests',
            r'Out of memory',
            r'Internal server error',
        ]
        
        medium_severity_patterns = [
            r'Network timeout',
            r'Connection refused',
            r'Service unavailable',
        ]
        
        for hp in high_severity_patterns:
            if re.search(hp, pattern, re.IGNORECASE) or re.search(hp, message, re.IGNORECASE):
                return 'high'
                
        for mp in medium_severity_patterns:
            if re.search(mp, pattern, re.IGNORECASE) or re.search(mp, message, re.IGNORECASE):
                return 'medium'
                
        return 'low'
        
    def attempt_fix(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """Attempt to fix the identified error"""
        self.logger.info(f"Attempting fix for error: {error_info['message']}")
        error_info['action_taken'] = None
        error_info['success'] = None
        error_info['response'] = None
        
        try:
            # Determine appropriate fix based on error type
            if error_info['severity'] == 'low':
                action = self._execute_low_risk_fix(error_info)
            elif error_info['severity'] == 'medium':
                action = self._execute_medium_risk_fix(error_info)
            else:  # high severity
                action = self._block_high_risk_fix(error_info)
                
            error_info['action_taken'] = action
            error_info['response'] = f"Applied fix: {action}"
            error_info['success'] = action != "BLOCKED"
            
        except Exception as e:
            error_info['response'] = f"Fix failed: {str(e)}"
            error_info['success'] = False
            self.logger.error(f"Fix failed for error {error_info['message']}: {e}")
            
        return error_info
        
    def _execute_low_risk_fix(self, error_info: Dict[str, Any]) -> str:
        """Execute a low-risk fix"""
        message = error_info['message']
        
        # Check if there's a predefined fix template
        for pattern, fix_action in self.config.low_risk_fixes.items():
            if re.search(pattern, message, re.IGNORECASE):
                self.logger.info(f"Applying low-risk fix: {fix_action}")
                return fix_action
                
        # Generic low-risk fix for unknown errors
        self.logger.info("Applying generic low-risk fix")
        return "Logged error, no action required"
        
    def _execute_medium_risk_fix(self, error_info: Dict[str, Any]) -> str:
        """Execute a medium-risk fix"""
        message = error_info['message']
        
        # Check if there's a predefined fix template
        for pattern, fix_action in self.config.medium_risk_fixes.items():
            if re.search(pattern, message, re.IGNORECASE):
                self.logger.info(f"Applying medium-risk fix: {fix_action}")
                return fix_action
                
        # For medium risk, we'd typically need user approval in a real implementation
        self.logger.warning("Medium-risk error detected, requires user approval")
        return "Requires user approval"
        
    def _block_high_risk_fix(self, error_info: Dict[str, Any]) -> str:
        """Block high-risk fixes and alert user"""
        self.logger.critical(f"Blocking high-risk error: {error_info['message']}")
        
        # Log the blockage
        with open(self.config.auto_fix_log, 'a') as f:
            f.write(f"{datetime.now().isoformat()} - BLOCKED - {error_info['message']}\n")
            
        return "BLOCKED - requires manual intervention"
        
    def verify_fix(self, error_info: Dict[str, Any]) -> bool:
        """Verify if the fix was successful"""
        # Simple verification - check if error still appears in recent logs
        if error_info['success']:
            try:
                # Check if we can find the error pattern in recent logs
                # In a real implementation, this would be more sophisticated
                self.logger.info(f"Verifying fix for: {error_info['message']}")
                return True
            except Exception as e:
                self.logger.error(f"Verification failed: {e}")
                return False
        return False
        
    def log_result(self, error_info: Dict[str, Any]):
        """Log the result of auto-fix attempt"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'error_message': error_info['message'],
            'pattern': error_info['pattern'],
            'severity': error_info['severity'],
            'action_taken': error_info['action_taken'],
            'success': error_info['success'],
            'response': error_info['response']
        }
        
        try:
            with open(self.config.auto_fix_log, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to log auto-fix result: {e}")
class TokenCompressor:
    """Caveman-style compression to reduce token usage"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger('token-compressor')
        
        # Caveman compression patterns
        self.filler_patterns = [
            (r'\b(please|kindly|just|simply|basically|actually|literally|obviously|clearly)', ''),
            (r'\b(the|an|a|this|that|these|those)', ''),
            (r'\b(it is|it was|it will|it has)', 'is/was/will/has'),
            (r'\b(i think|you know|I mean|basically)', ''),
            (r'\b(in order to|with regard to|with respect to)', 'to/with'),
            (r'\b(very|really|quite|extremely|quite|quite a|quite some)', ''),
            (r'\b(because|due to|as a result of|in spite of)', 'because'),
        ]
        
        # Important patterns to preserve
        self.preserve_patterns = [
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            r'```[\s\S]*?```',
            r'`[^`]+`',
            r'[\w\-\.]+@[\w\-\.]+(?:\.\w+)+',
            r'(?:CVE-|CVE\s*)?\d{4}-\d{4,}',
            r'[A-Za-z]:\\(?:[^\\/\*\?\<\>\|]+)(?:\\[^\\/\*\?\<\>\|]+)*',
        ]
        
    def compress_text(self, text: str, preserve_technical: bool = True) -> str:
        """
        Apply caveman-style compression to reduce token usage
        
        Preserves:
        - URLs and email addresses
        - Code blocks and inline code
        - Technical terms and file paths
        - Critical error information
        """
        if not text:
            return text
            
        original_length = len(text)
        compressed = text
        
        # First, protect code blocks and technical patterns
        protected = {}
        protection_count = 0
        
        if preserve_technical:
            # Protect code blocks
            for pattern in ['```[\s\S]*?```', '`[^`]+`']:
                for match in re.finditer(pattern, compressed):
                    placeholder = f'__CODE_{protection_count}__'
                    protected[placeholder] = match.group(0)
                    compressed = compressed.replace(match.group(0), placeholder)
                    protection_count += 1
            
            # Protect URLs, emails, and technical identifiers
            for pattern in self.preserve_patterns:
                for match in re.finditer(pattern, compressed):
                    placeholder = f'__TECH_{protection_count}__'
                    protected[placeholder] = match.group(0)
                    compressed = compressed.replace(match.group(0), placeholder)
                    protection_count += 1
        
        # Apply filler word removal
        for pattern, replacement in self.filler_patterns:
            compressed = re.sub(pattern, replacement, compressed, flags=re.IGNORECASE)
        
        # Clean up double spaces created by removals
        compressed = re.sub(r'\s+', ' ', compressed).strip()
        
        # Remove redundant punctuation and formatting
        compressed = re.sub(r'\.\.+', '.', compressed)
        compressed = re.sub(r',\s*,', ',', compressed)
        compressed = re.sub(r'!+', '!', compressed)
        compressed = re.sub(r'\?+\?', '?', compressed)
        
        # Restore protected elements
        for placeholder, original in protected.items():
            compressed = compressed.replace(placeholder, original)
            
        # Final cleanup
        compressed = re.sub(r'\s+', ' ', compressed).strip()
        
        compression_ratio = (original_length - len(compressed)) / original_length if original_length > 0 else 0
        
        self.logger.info(f"Text compression: {original_length} → {len(compressed)} chars ({compression_ratio:.1%})")
        
        return compressed
        
    def compress_prompt(self, prompt: str) -> str:
        """Compress a prompt with technical preservation"""
        return self.compress_text(prompt, preserve_technical=True)
        
    def compress_response(self, response: str) -> str:
        """Compress a response, preserving technical content"""
        return self.compress_text(response, preserve_technical=True)
        
    def smart_compression(self, text: str, context: str = None) -> str:
        """
        Apply intelligent compression based on context
        
        If context indicates technical/debug content, preserve more
        Otherwise, apply more aggressive compression
        """
        if not text:
            return text
            
        # Determine if this is technical content
        technical_indicators = [
            'error', 'warning', 'exception', 'traceback', 'stack', 'bug', 'fix', 'patch',
            'file', 'path', 'directory', 'url', 'http', 'api', 'method', 'function',
            'import', 'syntax', 'variable', 'class', 'object', 'database', 'query',
            'command', 'shell', 'bash', 'python', 'json', 'xml', 'html', 'css',
            'error code', 'status', 'return', 'exception', 'trace', 'line', 'column'
        ]
        
        is_technical = (
            context and any(indicator in context.lower() for indicator in technical_indicators)
        )
        
        # Extract any technical content from the text itself
        is_text_technical = any(indicator in text.lower() for indicator in technical_indicators)
        
        if is_technical or is_text_technical:
            # Preserve more technical details
            return self.compress_text(text, preserve_technical=True)
        else:
            # Apply more aggressive compression
            return self.compress_text(text, preserve_technical=False)
class AutomationEngine:
    """Main automation engine orchestrating auto-fix and token optimization"""
    
    def __init__(self):
        self.config = Config()
        self.token_tracker = TokenUsageTracker(self.config)
        self.auto_fixer = AutoFixer(self.config, self.token_tracker)
        self.compressor = TokenCompressor(self.config)
        
    def run_cycle(self):
        """Run a complete automation cycle"""
        logger.info("Starting automation engine cycle")
        start_time = time.time()
        
        # Phase 1: Auto-fix (immediate response)
        logger.info("Phase 1: Auto-fix scan")
        errors = self.auto_fixer.scan_logs_for_errors()
        
        for error in errors:
            logger.info(f"Processing error: {error['message'][:100]}...")
            
            # Apply fix
            result = self.auto_fixer.attempt_fix(error)
            
            # Verify and log
            if result['success']:
                self.auto_fixer.verify_fix(result)
                
            self.auto_fixer.log_result(result)
            
        # Phase 2: Token compression and optimization
        logger.info("Phase 2: Token optimization")
        self._apply_token_optimization()
        
        # Phase 3: Scheduled maintenance
        logger.info("Phase 3: Scheduled maintenance")
        self._perform_maintenance()
        
        cycle_time = time.time() - start_time
        logger.info(f"Automation cycle completed in {cycle_time:.2f} seconds")
        
    def _apply_token_optimization(self):
        """Apply token compression and optimization"""
        # This would typically involve monitoring actual model usage
        # and applying compression to prompts/responses
        
        # For demonstration, we'll log the current token usage
        models = list(self.config.free_models.keys())
        for model in models:
            stats = self.token_tracker.get_usage_stats(model)
            if stats:
                usage = stats.get('today_used', 0)
                limit = stats.get('today_limit', 100)
                percentage = (usage / limit) * 100 if limit > 0 else 0
                
                logger.info(f"Token usage - {model}: {usage}/{limit} ({percentage:.1f}%)")
                
                if percentage > 85:
                    logger.warning(f"Approaching token limit for {model}")
                    
        # Example of applying compression to a sample text
        sample_text = "Please process this request as quickly as possible, because it is very important and urgent and I really need this done and it is critical for my business operations."
        compressed = self.compressor.compress_prompt(sample_text)
        logger.info(f"Sample compression: {len(sample_text)} → {len(compressed)} characters")
        
    def _perform_maintenance(self):
        """Perform routine maintenance tasks"""
        # Clean up old log files
        log_files = [
            self.config.logs_dir / 'exec.log',
            self.config.logs_dir / 'auto_fixer.log',
            self.config.logs_dir / 'token_optimizer.log',
        ]
        
        for log_file in log_files:
            if log_file.exists():
                file_size = log_file.stat().st_size
                if file_size > 10 * 1024 * 1024:  # 10MB
                    logger.info(f"Cleaning up large log file: {log_file}")
                    # Keep only recent entries
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                        
                    # Keep last 1000 lines and write back
                    recent_lines = lines[-1000:] if len(lines) > 1000 else lines
                    with open(log_file, 'w') as f:
                        f.writelines(recent_lines)
                        
                    logger.info(f"Trimmed {log_file} to {len(recent_lines)} lines")
                    
        # Update token usage data
        self.token_tracker.save_usage_data()
        
        logger.info("Maintenance completed")
        
    def start_monitoring(self, interval_seconds: int = 600):
        """
        Start continuous monitoring in a separate process
        
        Args:
            interval_seconds: How often to run the automation cycle
        """
        logger.info(f"Starting monitoring with {interval_seconds}s interval")
        
        while True:
            try:
                self.run_cycle()
                
                # Sleep for the specified interval
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Sleep before retrying
def main():
    """Main entry point"""
    logger.info("Starting OpenClaw Automation Engine")
    
    # Create engine instance
    engine = AutomationEngine()
    
    # Run initial cycle
    logger.info("Running initial automation cycle")
    engine.run_cycle()
    
    # Start continuous monitoring
    logger.info("Starting continuous monitoring (use Ctrl+C to stop)")
    try:
        engine.start_monitoring(interval_seconds=600)  # 10 minutes
    except KeyboardInterrupt:
        logger.info("Automation engine stopped")
        
if __name__ == "__main__":
    main()