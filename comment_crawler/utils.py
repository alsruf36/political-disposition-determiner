import os
import logging
import logging.handlers

def CreateLogger(loggerName):
    logger = logging.getLogger(loggerName)
    if len(logger.handlers) > 0:
        return logger

    logPath = os.path.join(os.path.realpath(""), "logs", loggerName + ".log")
    Mkdirs(logPath)

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(filename)s:%(lineno)s] %(asctime)s > %(levelname)s | %(message)s')

    streamHandler = logging.StreamHandler()
    streamHandler.setLevel(logging.INFO)
    streamHandler.setFormatter(formatter)
    rotatingHandler = logging.handlers.RotatingFileHandler(logPath, maxBytes=1024 * 1024 * 1024)
    rotatingHandler.setLevel(logging.DEBUG)
    rotatingHandler.setFormatter(formatter)

    logger.addHandler(streamHandler)
    logger.addHandler(rotatingHandler)
    return logger

def Mkdirs(filePath):
    dirPath = os.path.sep.join(filePath.split(os.path.sep)[:-1])
    if not os.path.exists(dirPath):
        os.makedirs(dirPath, exist_ok = True)