import { useEffect } from 'react'
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import geojsonData from '../data/omsk_boundaries.json'

const BOUNDS = L.latLngBounds([[52.5, 68.0], [59.5, 78.0]])
const MIN_ZOOM = 6.5

function MapConstraints() {
  const map = useMap()
  useEffect(() => {
    map.setMinZoom(MIN_ZOOM)
    map.setMaxBounds(BOUNDS)
    map.options.bounceAtZoomLimits = false
    const clampZoom = () => {
      if (map.getZoom() < MIN_ZOOM) map.setZoom(MIN_ZOOM, { animate: false })
    }
    map.on('zoom', clampZoom)
    map.on('zoomend', clampZoom)
    return () => { map.off('zoom', clampZoom); map.off('zoomend', clampZoom) }
  }, [map])
  return null
}

const scoreToColor = (score) => {
  if (score == null) return '#cbd5e1'
  if (score >= 75) return '#22c55e'
  if (score >= 60) return '#84cc16'
  if (score >= 50) return '#f97316'
  if (score >= 35) return '#ef4444'
  return '#991b1b'
}

// Мягкое сопоставление: ищем district чьё имя входит в OSM name или наоборот
function matchDistrict(osmName, districts) {
  if (!osmName) return null
  const n = osmName.toLowerCase()
  const exact = districts.find(d => {
    const dn = d.name.toLowerCase()
      .replace(' округ', '').replace(' район', '').replace('ский', '').replace('ской', '')
    return n.includes(dn) || dn.includes(n.replace(' район', '').replace(' округ', ''))
  })
  if (exact) return exact
  if (n.includes('омск')) return districts.find(d => d.name.toLowerCase().includes('омский')) || null
  return null
}

export default function OmskMap({ districts, onDistrictClick, showTiles = true }) {

  const styleFeature = (feature) => {
    const district = matchDistrict(feature.properties?.name, districts)
    return {
      fillColor: scoreToColor(district?.score),
      fillOpacity: 0.5,
      color: '#9ca3af',
      weight: 1,
      opacity: 1,
    }
  }

  const onEachFeature = (feature, layer) => {
    const osmName = feature.properties?.name || ''
    const district = matchDistrict(osmName, districts)
    const label = district
      ? `${district.name} · скор ${district.score}`
      : osmName

    layer.bindTooltip(label, { sticky: true })

    layer.on({
      mouseover: (e) => e.target.setStyle({ fillOpacity: 0.7, weight: 2 }),
      mouseout: (e) => e.target.setStyle({ fillOpacity: 0.45, weight: 1 }),
      click: () => district && onDistrictClick(district),
    })
  }

  return (
    <MapContainer
      center={[55.8, 73.2]}
      zoom={6}
      zoomAnimation={true}
      maxBounds={BOUNDS}
      maxBoundsViscosity={3.0}
      bounceAtZoomLimits={false}
      inertia={false}
      style={{ height: '100%', width: '100%' }}
      zoomControl={false}
    >
      <MapConstraints />
      {showTiles && (
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; CARTO'
        />
      )}

      <GeoJSON
        key="static"
        data={geojsonData}
        style={styleFeature}
        onEachFeature={onEachFeature}
      />
    </MapContainer>
  )
}
