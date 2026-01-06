package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/driver/postgres"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

var db *gorm.DB

// initDatabase inicializa la conexión a la base de datos
func initDatabase() error {
	var err error
	var dialector gorm.Dialector

	switch appConfig.Database.Type {
	case "sqlite":
		// Crear directorio si no existe
		dbDir := filepath.Dir(appConfig.Database.Path)
		if err := os.MkdirAll(dbDir, 0755); err != nil {
			return fmt.Errorf("error creando directorio de BD: %v", err)
		}

		dialector = sqlite.Open(appConfig.Database.Path)
	case "postgres":
		dsn := fmt.Sprintf("host=%s user=%s password=%s dbname=%s port=%d sslmode=disable",
			appConfig.Database.Host,
			appConfig.Database.User,
			appConfig.Database.Password,
			appConfig.Database.Database,
			appConfig.Database.Port,
		)
		dialector = postgres.Open(dsn)
	case "mysql":
		dsn := fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?charset=utf8mb4&parseTime=True&loc=Local",
			appConfig.Database.User,
			appConfig.Database.Password,
			appConfig.Database.Host,
			appConfig.Database.Port,
			appConfig.Database.Database,
		)
		dialector = mysql.Open(dsn)
	default:
		return fmt.Errorf("tipo de base de datos no soportado: %s", appConfig.Database.Type)
	}

	// Configurar logger de GORM
	gormLogger := logger.Default
	if !appConfig.Server.Debug {
		gormLogger = logger.Default.LogMode(logger.Silent)
	}

	db, err = gorm.Open(dialector, &gorm.Config{
		Logger: gormLogger,
	})
	if err != nil {
		return fmt.Errorf("error conectando a la base de datos: %v", err)
	}

	// Auto-migrar modelos
	if err := autoMigrate(); err != nil {
		return fmt.Errorf("error en auto-migración: %v", err)
	}

	log.Println("✅ Base de datos inicializada correctamente")
	log.Printf("📁 Ubicación BD: %s", appConfig.Database.Path)
	return nil
}

// autoMigrate ejecuta las migraciones automáticas
func autoMigrate() error {
	return db.AutoMigrate(
		&User{},
		&SystemLog{},
		&SystemStatistic{},
		&NetworkConfig{},
		&VPNConfig{},
		&WireGuardConfig{},
		&AdBlockConfig{},
		&SystemConfig{},
	)
}

// SystemLog modelo para logs del sistema
type SystemLog struct {
	ID        uint      `gorm:"primaryKey"`
	Level     string    `gorm:"not null;index"`
	Message   string    `gorm:"type:text"`
	Source    string
	UserID    *int
	CreatedAt time.Time `gorm:"index"`
}

// SystemConfig modelo para configuraciones clave-valor
type SystemConfig struct {
	Key   string `gorm:"primaryKey"`
	Value string `gorm:"type:text"`
}

// SystemStatistic modelo para estadísticas
type SystemStatistic struct {
	ID        uint      `gorm:"primaryKey"`
	Type      string    `gorm:"not null;index"` // cpu_usage, memory_usage, disk_usage
	Value     float64   `gorm:"not null"`
	Timestamp time.Time `gorm:"index"`
}

// NetworkConfig configuración de red
type NetworkConfig struct {
	ID            uint   `gorm:"primaryKey"`
	Interface     string `gorm:"not null"`
	DHCPEnabled   bool   `gorm:"default:false"`
	DHCPRangeStart string
	DHCPRangeEnd   string
	Gateway        string
	DNSPrimary     string
	DNSSecondary   string
	UpdatedAt      time.Time
}

// VPNConfig configuración de VPN
type VPNConfig struct {
	ID        uint   `gorm:"primaryKey"`
	Type      string `gorm:"not null"` // openvpn, wireguard
	Config    string `gorm:"type:text"`
	IsActive  bool   `gorm:"default:false"`
	UpdatedAt time.Time
}

// WireGuardConfig configuración de WireGuard
type WireGuardConfig struct {
	ID          uint   `gorm:"primaryKey"`
	Interface   string `gorm:"not null"`
	PrivateKey  string
	PublicKey   string
	Address     string
	DNS         string
	IsActive    bool   `gorm:"default:false"`
	UpdatedAt   time.Time
}

// AdBlockConfig configuración de AdBlock
type AdBlockConfig struct {
	ID        uint   `gorm:"primaryKey"`
	Enabled   bool   `gorm:"default:false"`
	Lists     string `gorm:"type:text"` // JSON array de URLs
	UpdatedAt time.Time
}

// InsertLog inserta un log en la base de datos
func InsertLog(level, message, source string, userID *int) error {
	log := SystemLog{
		Level:   level,
		Message: message,
		Source:  source,
		UserID:  userID,
	}
	return db.Create(&log).Error
}

// GetLogs obtiene logs con paginación
func GetLogs(level string, limit, offset int) ([]SystemLog, int64, error) {
	var logs []SystemLog
	var total int64

	query := db.Model(&SystemLog{})
	if level != "" && level != "all" {
		query = query.Where("level = ?", level)
	}

	// Contar total
	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	// Obtener logs
	if err := query.Order("created_at DESC").Limit(limit).Offset(offset).Find(&logs).Error; err != nil {
		return nil, 0, err
	}

	return logs, total, nil
}

// InsertStatistic inserta una estadística
func InsertStatistic(statType string, value float64) error {
	stat := SystemStatistic{
		Type:      statType,
		Value:     value,
		Timestamp: time.Now(),
	}
	return db.Create(&stat).Error
}
