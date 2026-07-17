import psutil
import os
from logger import get_logger

# Получаем logger для модуля
logger = get_logger("ProcessManager")


def kill_processes(process_names, notification_callback=None):
    """
    Завершает процессы по списку имен

    Args:
        process_names: список имен процессов для завершения
        notification_callback: функция для показа уведомления при закрытии процесса

    Returns:
        список закрытых процессов
    """
    if not process_names:
        return []

    killed_processes = []
    processed_pids = set()  # Отслеживаем уже обработанные PID

    try:
        # Получаем список процессов один раз для эффективности
        processes = list(psutil.process_iter(['pid', 'name']))
        logger.debug(f"Получено {len(processes)} процессов для проверки")
    except Exception as e:
        logger.error(f"Не удалось получить список процессов: {e}")
        return []

    for proc in processes:
        try:
            # Пропускаем уже обработанные процессы
            pid = proc.info['pid']
            if pid in processed_pids:
                continue

            process_name = proc.info['name']

            # Проверяем, есть ли процесс в списке заблокированных
            for blocked_name in process_names:
                if process_name.lower() == blocked_name.lower():
                    # Отмечаем PID как обработанный
                    processed_pids.add(pid)

                    try:
                        # Пытаемся завершить процесс
                        logger.info(
                            f"Завершаем процесс '{process_name}' (PID: {pid})")
                        proc.kill()

                        # Ждем подтверждения завершения (с таймаутом)
                        try:
                            proc.wait(timeout=1)
                            logger.debug(
                                f"Процесс {pid} завершен через kill()")
                        except psutil.TimeoutExpired:
                            # Процесс не завершился за 1 секунду, пробуем
                            # terminate
                            logger.warning(
                                f"Процесс {pid} не завершился через kill(), пробуем terminate()")
                            try:
                                proc.terminate()
                                proc.wait(timeout=2)
                                logger.debug(
                                    f"Процесс {pid} завершен через terminate()")
                            except BaseException:
                                logger.error(
                                    f"Процесс {pid} не удалось завершить даже через terminate()")

                        killed_processes.append(process_name)

                        # Показываем уведомление если передан callback
                        if notification_callback:
                            try:
                                notification_callback(process_name)
                            except Exception as callback_error:
                                logger.error(
                                    f"Ошибка в callback для '{process_name}': {callback_error}")

                    except psutil.NoSuchProcess:
                        # Процесс уже завершился
                        logger.debug(
                            f"Процесс '{process_name}' (PID: {pid}) уже завершен")
                    except psutil.AccessDenied:
                        # Нет прав для завершения
                        logger.warning(
                            f"Нет прав для завершения '{process_name}' (PID: {pid})")
                    except Exception as kill_error:
                        logger.error(
                            f"Не удалось завершить '{process_name}' (PID: {pid}): {kill_error}")

                    break  # Переходим к следующему процессу

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Игнорируем процессы, которые уже не существуют или к которым нет
            # доступа
            continue
        except Exception as e:
            logger.error(f"Ошибка при обработке процесса: {e}")
            continue

    if killed_processes:
        logger.info(f"Всего завершено процессов: {len(killed_processes)}")

    return killed_processes


def get_running_processes():
    """
    Возвращает список всех запущенных процессов

    Returns:
        список словарей с информацией о процессах
    """
    processes = []

    for proc in psutil.process_iter(['pid', 'name', 'username']):
        try:
            processes.append({
                'pid': proc.info['pid'],
                'name': proc.info['name'],
                'username': proc.info['username']
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return processes


def is_process_running(process_name):
    """
    Проверяет, запущен ли процесс с заданным именем

    Args:
        process_name: имя процесса для проверки

    Returns:
        True если процесс запущен, иначе False
    """
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'].lower() == process_name.lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return False


if __name__ == "__main__":
    # Тест модуля
    print("Запущенные процессы:")
    for proc in get_running_processes()[:10]:  # Показываем первые 10
        print(f"  {proc['name']} (PID: {proc['pid']})")
