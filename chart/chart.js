var margin = {top: 20, right: 30, bottom: 30, left: 50};
var height = 300 - (margin.top + margin.bottom);
var barWidth = 20;

var yScale = d3.scaleLinear()
    .range([height, 0]);
var xScale = d3.scaleBand();

var xAxis = d3.axisBottom(xScale);
var yAxis = d3.axisLeft(yScale);

var container = d3.select("#d3chart")
    .attr("height", height + margin.top + margin.bottom);

d3.csv(
    "chart.csv",
    function(d) {
      d.p = +d.p;
      d.p_5 = +d.p_5;
      d.p_95 = +d.p_95;
      return d;
    },
    function(error, data) {
      if (error) {
        console.log(error);
        return;
      }

      var chartWidth = data.length * barWidth;
      var containerWidth = chartWidth + margin.left + margin.right;
      xScale
          .domain(data.map(function(d) { return d.side; }))
          .range([0, chartWidth]);

      var fairValue = 1.0 / data.length;
      var maxValue = d3.max(data, function(d) { return d.p_95; });
      yScale.domain([0, maxValue]);
      yAxis.tickSizeInner(-chartWidth);

      var chart = container
          .attr("width", containerWidth)
          .append("g")
              .attr("transform", `translate(${margin.left}, ${margin.top})`);

      chart.append("g")
          .attr("class", "y axis")
          .attr("transform", `translate(-2, 0)`)
          .call(yAxis)
          .append("text")
              .attr("transform", "rotate(-90)")
              .attr("y", -45)
              .attr("x", -yScale(maxValue / 2))
              .attr("dy", "0.71em")
              .style("text-anchor", "middle")
              .text("Frequency");
      chart.append("line")
          .attr("class", "fair")
          .attr("x1", 0)
          .attr("x2", chartWidth)
          .attr("y1", yScale(fairValue))
          .attr("y2", yScale(fairValue))
          .attr("width", chartWidth);

      chart.append("g")
          .attr("class", "x axis")
          .attr("transform", `translate(0, ${height + 1})`)
          .call(xAxis)
          .append("text")
              .text("Side")
              .attr("x", chartWidth / 2)
              .attr("y", 29)
              .style("text-andhor", "middle");

      var bar = chart.selectAll("g.bar")
          .data(data)
          .enter().append("g")
              .attr("class", "bar")
              .attr("transform", function(d, i) {
                  return `translate(${xScale(+d.side)}, 0)`; });

      bar.append("rect")
          .attr("width", barWidth - 1)
          .attr("height", function(d) { return height - yScale(d.p); })
          .attr("y", function(d) { return yScale(d.p); })
          .attr("title", function(d) { return d.p; });

      bar.append("text")
          .attr("x", barWidth / 2)
          .attr("y", yScale(0))
          .attr("dx", "0.35em")
          .attr("dy", "-0.35em")
          .text(function(d) { return d.side; });

      bar.append("path")
          .attr("d", function(d) { return "" +
              `M ${barWidth / 2 - 3} ${yScale(d.p_5)}` +
              `L ${barWidth / 2 + 3} ${yScale(d.p_5)}` +
              `M ${barWidth / 2} ${yScale(d.p_5)}` +
              `L ${barWidth / 2} ${yScale(d.p_95)}` +
              `M ${barWidth / 2 - 3} ${yScale(d.p_95)}` +
              `L ${barWidth / 2 + 3} ${yScale(d.p_95)}`; })
          .attr("class", "ci");
});
