# Utilidad para obtener logs de la aplicación
import datetime

def get_logs(log_file='logs/hostberry.log'):
    logs = []
    try:
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=24)
        with open(log_file, 'r') as f:
            for line in f.readlines()[-100:]:
                line = line.strip()
                if line:
                    parts = line.split(' ', 3)
                    if len(parts) >= 4:
                        try:
                            log_time = datetime.datetime.strptime(parts[0] + ' ' + parts[1], '%Y-%m-%d %H:%M:%S,%f')
                            if log_time > cutoff_time:
                                logs.append({'timestamp': ' '.join(parts[:2]), 'message': parts[3]})
                        except ValueError:
                            logs.append({'timestamp': '', 'message': line})
                    else:
                        logs.append({'timestamp': '', 'message': line})
    except FileNotFoundError:
        pass
    return list(reversed(logs))
