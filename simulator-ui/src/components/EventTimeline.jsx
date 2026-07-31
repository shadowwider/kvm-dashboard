export default function EventTimeline({ events }) {
  return (
    <section className="timeline">
      <div className="panel-title">Event timeline</div>
      <div className="timeline-scroll">
        {events.map(event => (
          <div className="timeline-event" key={event.id}>
            <span>{new Date(event.time).toLocaleTimeString()}</span>
            <strong>{event.type}</strong>
            <p>{event.message || event.summary || JSON.stringify(event.payload || event.data || event).slice(0, 160)}</p>
          </div>
        ))}
        {!events.length && <div className="empty">Waiting for REST actions or /api/v1/ws runtime events.</div>}
      </div>
    </section>
  );
}
