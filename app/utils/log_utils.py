# Utilidad para obtener logs de la aplicación
import datetime

def get_logs(log_file='logs/hostberry.log'):
    logs = []
    try:
        # Ensure logs directory exists
        import os
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # Create the file if it doesn't exist
        if not os.path.exists(log_file):
            with open(log_file, 'w') as f:
                f.write('')
        
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=24)
        with open(log_file, 'r') as f:
            for line in f.readlines()[-100:]:  # Read last 100 lines
                line = line.strip()
                if line:
                    parts = line.split(' ', 3)
                    if len(parts) >= 4:
                        try:
                            log_time = datetime.datetime.strptime(parts[0] + ' ' + parts[1], '%Y-%m-%d %H:%M:%S,%f')
                            if log_time > cutoff_time:
                                logs.append({'timestamp': ' '.join(parts[:2]), 'message': parts[3]})
                        except ValueError:
                            # If timestamp parsing fails, just add the raw line
                            logs.append({'timestamp': '', 'message': line})
                    else:
                        logs.append({'timestamp': '', 'message': line})
    except Exception as e:
        print(f"Error reading logs: {e}")
        # Return empty list if there's an error
        return []
        
    return list(reversed(logs))
