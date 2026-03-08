Fork de (https://github.com/MiguelAngelLV/ha-octopus-spain)
# Componente Octopus Spain para Home Assistant

## ¿Qué es Octopus Energy?

[Octopus Energy](https://octopusenergy.es/) es una comercializadora eléctrica española.

Entre otras ventajas, dispone de la **Solar Wallet**, un servicio que permite acumular crédito obtenido
por los excedentes solares para reducir a 0€ la factura así como acumular para posteriores facturas.


## ¿Qué hace el componente Octopus Spain?

Este componente conecta con tu cuenta de _Octopus Energy_ para obtener el estado actual de tu **Solar Wallet** 
así como los datos básicos de última factura.

Este componente ha sido revisado por los ingenerios de _Octopus Energy_ y ha recibido su visto bueno.

## Instalación

Puedes instalar el componente usando HACS:

### Directa usando _My Home Assistant_
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mandinger&repository=fork-ha-octopus-spain&category=integration)


### Manual
```
HACS -> Integraciones -> Tres puntitos -> Repositorios Personalizados
```
Copias la URL del repositorio ( https://github.com/mandinger/fork-ha-octopus-spain ), como categoría seleccionas _Integración_ y pulsas en _Añadir_.


## Configuración

Una vez instalado, ve a _Dispositivos y Servicios -> Añadir Integración_ y busca _Octopus_.

Durante la configuración podrás elegir el tipo de autenticación:
- Credenciales (email y contraseña)
- API Key

Si eliges API Key, introduce tu api key (detalles en como obtener api key en octopus españa mas adelante); no se requiere email/contraseña. Podrás cambiar el método más tarde desde las Opciones de la integración. Para más información sobre tu cuenta, consulta [Octopus Energy](https://octopusenergy.es/).



## Entidades
Una vez configurado el componente, tendrás dos entidades por cada cuenta que tengas asociada a tu email (normalmente una).

### Solar Wallet
La entidad Solar Wallet devuelve el valor actual de tu Solar Wallet. Este valor (en euros) estará actualizado al de tu última factura. Actualmente no se puede consultar en tiempo real.

## Octopus Credit
La entidad Octopus Credit devuelve el valor actual de tu crédito en Octopus obtenido por cuentas referedidas u otras posibles bonificaciones.

### Última Factura
Esta entidad devuelve el coste de tu última factura.

Adicionalmente, en los atributos, están disponibles las fechas de emisión de esa factura así el periodo (inicio y final) de la misma.

### Sensores de Factura (individuales)
Además del sensor agregado "Última Factura Octopus", el componente expone sensores individuales para cada campo de la última factura. Esto facilita su uso directo en tarjetas, automatizaciones y gráficos:

- sensor.factura_importe_facturado: Importe facturado (€)
- sensor.factura_total_bruto: Total bruto (€)
- sensor.factura_total_neto: Total neto (€)
- sensor.factura_impuestos: Impuestos (€)
- sensor.factura_emitida: Fecha de emisión (fecha)
- sensor.factura_inicio_cargos: Inicio de cargos (fecha)
- sensor.factura_pdf: Estado del PDF (atributo url con el enlace)
- sensor.factura_id: Identificador de la factura

Nota: Si tienes varias cuentas en Octopus, los nombres visibles de las entidades incluirán el identificador de la cuenta entre paréntesis, p. ej. "Factura (mi_cuenta): Total neto".

Para ver una tarjeta de ejemplo con estos sensores, consulta el panel de muestra en [ha/dashboard.yml](ha/dashboard.yml).


## Consumo eléctrico (estadísticas)
El componente no ofrece consumo en tiempo real. En su lugar, importa de forma retroactiva los datos horarios de consumo facilitados por Octopus y los inserta en el sistema de estadísticas de Home Assistant.

- Fuente: datos horarios (hourly) de consumo por cuenta.
- Funcionamiento: en cada actualización se añaden las horas faltantes desde la última hora importada. Si no existen estadísticas previas, se inicia desde el día 1 del mes actual (UTC).
- Tipo de dato: estadística externa con suma acumulada por hora.
- Unidad: kWh.
- Identificador de estadística (`statistic_id`): `octopus_spain:energy_consumption_<cuenta_slug>`.
- Nombre mostrado en HA: "Consumo Electrico" o "Consumo Electrico (<cuenta>)" cuando hay varias cuentas.

Uso en interfaz:
- Tarjeta "Gráfico de estadísticas": selecciona la estadística con el nombre anterior para visualizar la serie acumulada por horas.
- Panel de Energía: puedes seleccionar esta estadística como fuente de consumo (al ser kWh con suma acumulada y marcada como externa).
- Mas detalles pendientes de documentación.

## Uso

Podrás usar estas etidades para visualizar el estado así como crear automatizaciones para informate, por ejemplo, 
cuando se produzca un cambio en el atributo "Emitida" de última fáctura.


Ejemplo de panel (dashboard):

Puedes encontrar un panel de ejemplo listo para usar en [ha/dashboard.yml](ha/dashboard.yml). Copia su contenido en tu dashboard (modo YAML) o adáptalo a tus necesidades.

![card.png](img/card.png)

