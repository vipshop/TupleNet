package logger

import (
	"os"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
	"gopkg.in/natefinch/lumberjack.v2"
	"strconv"
)

// http://www.manongjc.com/article/45867.html
const (
	defaultLogPath  = "/var/log/tp-ui.log"
	defaultLogNum   = 10
	defaultLogAge   = 7
	defaultLogLevel = "INFO"
)

var newLogger *zap.SugaredLogger

var levelMap = map[string]zapcore.Level{
	"DEBUG":  zapcore.DebugLevel,
	"INFO":   zapcore.InfoLevel,
	"WARN":   zapcore.WarnLevel,
	"ERROR":  zapcore.ErrorLevel,
	"DPANIC": zapcore.DPanicLevel,
	"PANIC":  zapcore.PanicLevel,
	"FATAL":  zapcore.FatalLevel,
}

func getLoggerLevel(lvl string) zapcore.Level {
	if level, ok := levelMap[lvl]; ok {
		return level
	}
	return zapcore.InfoLevel
}

func init() {
	// set log path
	var logNum, logAge int
	logPath := os.Getenv("LOG_PATH")
	if logPath == "" {
		logPath = defaultLogPath
	}
	logNumStr := os.Getenv("LOG_NUM")
	if logNumStr == "" {
		logNum = defaultLogNum
	} else {
		logNum, _ = strconv.Atoi(logNumStr)
	}
	logAgeStr := os.Getenv("LOG_AGE")
	if logAgeStr == "" {
		logNum = defaultLogAge
	} else {
		logNum, _ = strconv.Atoi(logAgeStr)
	}
	logLevel := os.Getenv("LOG_LEVEL")
	if logLevel == "" {
		logLevel = defaultLogLevel
	}
	level := getLoggerLevel(logLevel)
	syncWriter := zapcore.AddSync(&lumberjack.Logger{
		Filename:   logPath,
		MaxSize:    10240, // megabytes 10Gb
		MaxBackups: logNum,
		MaxAge:     logAge,
		LocalTime:  true,
		Compress:   true,
	})
	encoder := zap.NewProductionEncoderConfig()
	encoder.EncodeTime = zapcore.ISO8601TimeEncoder
	core := zapcore.NewCore(zapcore.NewConsoleEncoder(encoder), syncWriter, zap.NewAtomicLevelAt(level))
	logger := zap.New(core, zap.AddCaller(), zap.AddCallerSkip(1))
	newLogger = logger.Sugar()
}

func Debug(args ... interface{}) {
	newLogger.Debug(args...)
}

func Debugf(template string, args ... interface{}) {
	newLogger.Debugf(template, args...)
}

func Info(args ... interface{}) {
	newLogger.Info(args...)
}

func Infof(template string, args ... interface{}) {
	newLogger.Infof(template, args...)
}

func Warn(args ... interface{}) {
	newLogger.Warn(args...)
}

func Warnf(template string, args ... interface{}) {
	newLogger.Warnf(template, args...)
}

func Error(args ... interface{}) {
	newLogger.Error(args...)
}

func Errorf(template string, args ... interface{}) {
	newLogger.Errorf(template, args...)
}

func DPanic(args ... interface{}) {
	newLogger.DPanic(args...)
}

func DPanicf(template string, args ... interface{}) {
	newLogger.DPanicf(template, args...)
}

func Panic(args ... interface{}) {
	newLogger.Panic(args...)
}

func Panicf(template string, args ...interface{}) {
	newLogger.Panicf(template, args...)
}

func Fatal(args ...interface{}) {
	newLogger.Fatal(args...)
}

func Fatalf(template string, args ...interface{}) {
	newLogger.Fatalf(template, args...)
}
