package main

import (
	"errors"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"golang.org/x/crypto/bcrypt"
)

// Claims estructura para JWT
type Claims struct {
	Username string `json:"username"`
	UserID   int    `json:"user_id"`
	jwt.RegisteredClaims
}

// User estructura de usuario
type User struct {
	ID       int    `gorm:"primaryKey"`
	Username string `gorm:"unique;not null"`
	Password string `gorm:"not null"`
	Email    string
	IsActive bool   `gorm:"default:true"`
	CreatedAt time.Time
	UpdatedAt time.Time
}

// GenerateToken genera un token JWT para el usuario
func GenerateToken(user *User) (string, error) {
	expirationTime := time.Now().Add(time.Duration(appConfig.Security.TokenExpiry) * time.Minute)
	
	claims := &Claims{
		Username: user.Username,
		UserID:   user.ID,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(expirationTime),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
			NotBefore: jwt.NewNumericDate(time.Now()),
			Issuer:    "hostberry",
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString([]byte(appConfig.Security.JWTSecret))
}

// ValidateToken valida un token JWT
func ValidateToken(tokenString string) (*Claims, error) {
	claims := &Claims{}
	
	token, err := jwt.ParseWithClaims(tokenString, claims, func(token *jwt.Token) (interface{}, error) {
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, errors.New("método de firma inválido")
		}
		return []byte(appConfig.Security.JWTSecret), nil
	})

	if err != nil {
		return nil, err
	}

	if !token.Valid {
		return nil, errors.New("token inválido")
	}

	return claims, nil
}

// HashPassword hashea una contraseña usando bcrypt
func HashPassword(password string) (string, error) {
	bytes, err := bcrypt.GenerateFromPassword([]byte(password), appConfig.Security.BcryptCost)
	return string(bytes), err
}

// CheckPassword verifica una contraseña contra un hash
func CheckPassword(password, hash string) bool {
	err := bcrypt.CompareHashAndPassword([]byte(hash), []byte(password))
	return err == nil
}

// Login autentica un usuario
func Login(username, password string) (*User, string, error) {
	var user User
	if err := db.Where("username = ? AND is_active = ?", username, true).First(&user).Error; err != nil {
		return nil, "", errors.New("usuario o contraseña incorrectos")
	}

	if !CheckPassword(password, user.Password) {
		return nil, "", errors.New("usuario o contraseña incorrectos")
	}

	token, err := GenerateToken(&user)
	if err != nil {
		return nil, "", err
	}

	return &user, token, nil
}

// Register crea un nuevo usuario
func Register(username, password, email string) (*User, error) {
	// Validar username
	if username == "" {
		return nil, errors.New("el nombre de usuario no puede estar vacío")
	}
	
	// Validar password
	if password == "" {
		return nil, errors.New("la contraseña no puede estar vacía")
	}
	
	// Verificar si el usuario ya existe
	var existingUser User
	if err := db.Where("username = ?", username).First(&existingUser).Error; err == nil {
		return nil, errors.New("el usuario ya existe")
	}

	// Hashear contraseña
	hashedPassword, err := HashPassword(password)
	if err != nil {
		return nil, fmt.Errorf("error hasheando contraseña: %v", err)
	}

	user := User{
		Username: username,
		Password: hashedPassword,
		Email:    email,
		IsActive: true,
	}

	if err := db.Create(&user).Error; err != nil {
		return nil, fmt.Errorf("error creando usuario en BD: %v", err)
	}

	return &user, nil
}
