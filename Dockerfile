# Build stage
FROM golang:1.21-alpine AS builder

WORKDIR /app

# Instalar dependencias del sistema
RUN apk add --no-cache gcc musl-dev sqlite-dev

# Copiar archivos de dependencias
COPY go.mod go.sum ./
RUN go mod download

# Copiar código fuente
COPY . .

# Compilar la aplicación
RUN CGO_ENABLED=1 GOOS=linux go build -a -installsuffix cgo -o hostberry .

# Runtime stage
FROM alpine:latest

WORKDIR /app

# Instalar dependencias de runtime
RUN apk add --no-cache ca-certificates sqlite tzdata

# Copiar binario desde builder
COPY --from=builder /app/hostberry .

# Copiar archivos necesarios
COPY --from=builder /app/website ./website
COPY --from=builder /app/locales ./locales
COPY --from=builder /app/lua ./lua
COPY --from=builder /app/config.yaml.example ./config.yaml.example

# Crear directorio para datos
RUN mkdir -p /app/data

# Exponer puerto
EXPOSE 8000

# Variables de entorno
ENV GIN_MODE=release
ENV PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8000/health || exit 1

# Ejecutar aplicación
CMD ["./hostberry"]
